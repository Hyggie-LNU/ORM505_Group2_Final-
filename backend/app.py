import json
import threading
from datetime import datetime

import werkzeug.serving as _werkzeug_serving
from flask import Flask, request, jsonify
from flask_sock import Sock
from flask_sqlalchemy import SQLAlchemy

# ponytail: flask-socketio 4.3.2 导入时要 werkzeug.serving.run_with_reloader，2.2 起改到 _reloader。离开 EIO3 这组依赖后删掉。
if not hasattr(_werkzeug_serving, "run_with_reloader"):
    from werkzeug._reloader import run_with_reloader
    _werkzeug_serving.run_with_reloader = run_with_reloader

from flask_socketio import SocketIO, emit, join_room, leave_room
from sqlalchemy import text
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'  # 数据库文件会自动生成在项目文件夹里
app.config['SECRET_KEY'] = 'change-me-in-report-demo'  # Socket.IO 会话需要
db = SQLAlchemy(app)

socketio = SocketIO(
    app,
    cors_allowed_origins='*',
    async_mode='threading',
    logger=True,
    engineio_logger=False,
    # 先向手机确认连接，再执行下面的 connect。否则 server_hello 会抢在确认之前，手机会每 10 秒重连。
    always_connect=True,
)

# sid -> user_id，用于断线时知道是谁下线
online_users = {}
sock = Sock(app)
# ponytail: one lock for every phone socket; split per user if a send stalls receive
_ws_lock = threading.Lock()
_ws_clients = {}

# 定义用户表结构
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    phone = db.Column(db.String(20))
    
# 好友请求表：记录申请中/已同意/已拒绝的关系
class FriendRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    from_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    to_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    status = db.Column(db.String(20), default='pending')  # pending / accepted / rejected

# 好友关系表：双方都同意后，写入这张表，代表已经是好友（一人一行，禁止重复）
class Friend(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    friend_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    __table_args__ = (
        db.UniqueConstraint('user_id', 'friend_id', name='uq_friend_user_friend'),
    )

# 私聊消息表（双方共用一份记录；每人看到哪些由 ChatThread.cleared_before_id 决定）
class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    from_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    to_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    content = db.Column(db.String(2000), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    is_read = db.Column(db.Boolean, default=False)


# 每人自己的「最近聊天」列表（类似 QQ 消息页），双方各有一条
class ChatThread(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    friend_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    is_hidden = db.Column(db.Boolean, default=False)  # True = 不显示该聊天
    last_read_message_id = db.Column(db.Integer, default=0)
    cleared_before_id = db.Column(db.Integer, default=0)  # 删除记录后，只看比这个 id 更新的消息
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)
    __table_args__ = (
        db.UniqueConstraint('user_id', 'friend_id', name='uq_chat_thread_user_friend'),
    )


# 第一次运行时自动创建数据库表，并清掉历史上重复的好友行
with app.app_context():
    db.create_all()
    db.session.execute(text("""
        DELETE FROM friend
        WHERE id NOT IN (
            SELECT id FROM (
                SELECT MIN(id) AS id FROM friend GROUP BY user_id, friend_id
            )
        )
    """))
    db.session.commit()
    db.session.execute(text(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_friend_user_friend ON friend (user_id, friend_id)"
    ))
    db.session.commit()


def as_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def are_friends(a_id, b_id):
    a_id, b_id = as_int(a_id), as_int(b_id)
    if not a_id or not b_id:
        return False
    return Friend.query.filter_by(user_id=a_id, friend_id=b_id).first() is not None


def ensure_friend_link(user_id, friend_id):
    if user_id == friend_id:
        return
    if Friend.query.filter_by(user_id=user_id, friend_id=friend_id).first() is None:
        db.session.add(Friend(user_id=user_id, friend_id=friend_id))


def message_to_dict(msg):
    sender = User.query.get(msg.from_id)
    return {
        'id': msg.id,
        'from_id': msg.from_id,
        'to_id': msg.to_id,
        'from_username': sender.username if sender else '',
        'content': msg.content,
        'timestamp': msg.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
    }


def pair_message_filter(user_id, friend_id):
    return (
        ((Message.from_id == user_id) & (Message.to_id == friend_id))
        | ((Message.from_id == friend_id) & (Message.to_id == user_id))
    )


def get_or_create_thread(user_id, friend_id):
    thread = ChatThread.query.filter_by(user_id=user_id, friend_id=friend_id).first()
    if thread is None:
        thread = ChatThread(user_id=user_id, friend_id=friend_id)
        db.session.add(thread)
        db.session.flush()
    return thread


def last_visible_message(thread):
    return (
        Message.query.filter(
            pair_message_filter(thread.user_id, thread.friend_id),
            Message.id > thread.cleared_before_id,
        )
        .order_by(Message.id.desc())
        .first()
    )


def unread_count(thread):
    return Message.query.filter(
        Message.from_id == thread.friend_id,
        Message.to_id == thread.user_id,
        Message.id > thread.last_read_message_id,
        Message.id > thread.cleared_before_id,
    ).count()


def thread_to_dict(thread):
    friend = User.query.get(thread.friend_id)
    last = last_visible_message(thread)
    return {
        'friend_id': thread.friend_id,
        'username': friend.username if friend else '未知用户',
        'last_content': last.content if last else '',
        'last_timestamp': last.timestamp.strftime('%Y-%m-%d %H:%M:%S') if last else '',
        'unread_count': unread_count(thread),
    }


# 注册接口
@app.route('/register', methods=['POST'])
def register():
    # data = request.get_json()  # 接收App发来的JSON数据
    # 绕开App Inventor默认发送text/plain
    data = request.get_json(force=True)
    username = data.get('username')
    password = data.get('password')
    phone = data.get('phone', '')

    if not username or not password:
        return jsonify({"success": False, "message": "用户名或密码不能为空"})

    # 检查用户名是否已存在
    existing_user = User.query.filter_by(username=username).first()
    if existing_user:
        return jsonify({"success": False, "message": "用户名已存在"})

    # 密码加密后存储（绝不能存明文密码！）
    hashed_password = generate_password_hash(password)
    new_user = User(username=username, password_hash=hashed_password, phone=phone)
    db.session.add(new_user)
    db.session.commit()

    return jsonify({"success": True, "message": "注册成功"})

# 登录接口
@app.route('/login', methods=['POST'])
def login():
    # 绕开App Inventor默认发送text/plain
    data = request.get_json(force=True)
    username = data.get('username')
    password = data.get('password')

    user = User.query.filter_by(username=username).first()
    if not user:
        return jsonify({"success": False, "message": "用户不存在"})

    if not check_password_hash(user.password_hash, password):
        return jsonify({"success": False, "message": "密码错误"})

    return jsonify({"success": True, "message": "登录成功", "user_id": user.id})

# 搜索用户
@app.route('/search_user', methods=['GET'])
def search_user():
    keyword = request.args.get('keyword', '')
    if not keyword:
        return jsonify({"success": False, "message": "请输入用户名"})

    user = User.query.filter_by(username=keyword).first()
    if not user:
        return jsonify({"success": False, "message": "未找到该用户"})

    return jsonify({"success": True, "user_id": user.id, "username": user.username})

# 发送好友请求
@app.route('/add_friend', methods=['POST'])
def add_friend():
    data = request.get_json(force=True)
    from_id = as_int(data.get('from_id'))
    to_id = as_int(data.get('to_id'))

    if not from_id or not to_id:
        return jsonify({"success": False, "message": "参数缺失"})

    if from_id == to_id:
        return jsonify({"success": False, "message": "不能添加自己为好友"})

    # 检查是否已经是好友
    if are_friends(from_id, to_id):
        return jsonify({"success": False, "message": "你们已经是好友"})

    # 检查是否已经发送过申请（避免重复申请）
    existing_request = FriendRequest.query.filter_by(
        from_id=from_id, to_id=to_id, status='pending'
    ).first()
    if existing_request:
        return jsonify({"success": False, "message": "已发送过申请，请等待对方处理"})

    new_request = FriendRequest(from_id=from_id, to_id=to_id, status='pending')
    db.session.add(new_request)
    db.session.commit()

    return jsonify({"success": True, "message": "好友申请已发送"})

# 获取某用户收到的、待处理的好友请求
@app.route('/friend_requests', methods=['GET'])
def get_friend_requests():
    user_id = request.args.get('user_id', type=int)
    if not user_id:
        return jsonify({"success": False, "message": "参数缺失"})

    requests_list = FriendRequest.query.filter_by(to_id=user_id, status='pending').all()

    result = []
    for req in requests_list:
        from_user = User.query.get(req.from_id)
        result.append({
            "request_id": req.id,
            "from_id": req.from_id,
            "from_username": from_user.username if from_user else "未知用户"
        })

    return jsonify({"success": True, "requests": result})

# 处理好友请求（同意或拒绝）
@app.route('/respond_friend_request', methods=['POST'])
def respond_friend_request():
    data = request.get_json(force=True)
    request_id = as_int(data.get('request_id'))
    action = data.get('action')  # "accept" 或 "reject"

    friend_request = FriendRequest.query.get(request_id)
    if not friend_request:
        return jsonify({"success": False, "message": "请求不存在"})

    if friend_request.status != 'pending':
        return jsonify({"success": False, "message": "该申请已经处理过"})

    if action == 'accept':
        friend_request.status = 'accepted'
        # 双向各写一行；已存在则跳过，避免重复
        ensure_friend_link(friend_request.from_id, friend_request.to_id)
        ensure_friend_link(friend_request.to_id, friend_request.from_id)
    elif action == 'reject':
        friend_request.status = 'rejected'
    else:
        return jsonify({"success": False, "message": "action参数无效"})

    db.session.commit()
    return jsonify({"success": True, "message": "处理成功"})

# 获取好友列表
@app.route('/friend_list', methods=['GET'])
def get_friend_list():
    user_id = request.args.get('user_id', type=int)
    if not user_id:
        return jsonify({"success": False, "message": "参数缺失"})

    rows = (
        db.session.query(Friend.friend_id)
        .filter_by(user_id=user_id)
        .distinct()
        .all()
    )

    result = []
    for (friend_id,) in rows:
        friend_user = User.query.get(friend_id)
        result.append({
            "friend_id": friend_id,
            "username": friend_user.username if friend_user else "未知用户"
        })

    return jsonify({"success": True, "friends": result})


@app.route('/chat_history', methods=['GET'])
def chat_history():
    user_id = request.args.get('user_id', type=int)
    friend_id = request.args.get('friend_id', type=int)
    limit = request.args.get('limit', default=50, type=int)

    if not user_id or not friend_id:
        return jsonify({"success": False, "message": "参数缺失"})

    if not are_friends(user_id, friend_id):
        return jsonify({"success": False, "message": "你们还不是好友"})

    thread = ChatThread.query.filter_by(user_id=user_id, friend_id=friend_id).first()
    cleared_before = thread.cleared_before_id if thread else 0

    rows = (
        Message.query.filter(
            pair_message_filter(user_id, friend_id),
            Message.id > cleared_before,
        )
        .order_by(Message.id.desc())
        .limit(min(limit, 200))
        .all()
    )
    rows.reverse()  # 转成从旧到新，方便 ListView 从上往下读

    return jsonify({
        "success": True,
        "messages": [message_to_dict(m) for m in rows],
    })


@app.route('/start_chat', methods=['POST'])
def start_chat():
    """从好友列表「开始聊天」：把该好友放进我的 ChatList（不删记录）。"""
    data = request.get_json(force=True)
    user_id = data.get('user_id')
    friend_id = data.get('friend_id')

    if not user_id or not friend_id:
        return jsonify({"success": False, "message": "参数缺失"})

    user_id, friend_id = int(user_id), int(friend_id)
    if user_id == friend_id:
        return jsonify({"success": False, "message": "不能和自己聊天"})
    if not are_friends(user_id, friend_id):
        return jsonify({"success": False, "message": "你们还不是好友"})

    thread = get_or_create_thread(user_id, friend_id)
    thread.is_hidden = False
    thread.updated_at = datetime.utcnow()
    db.session.commit()

    return jsonify({"success": True, "message": "已加入聊天列表", "chat": thread_to_dict(thread)})


@app.route('/chat_list', methods=['GET'])
def chat_list():
    user_id = request.args.get('user_id', type=int)
    if not user_id:
        return jsonify({"success": False, "message": "参数缺失"})

    threads = (
        ChatThread.query.filter_by(user_id=user_id, is_hidden=False)
        .order_by(ChatThread.updated_at.desc())
        .all()
    )
    return jsonify({
        "success": True,
        "chats": [thread_to_dict(t) for t in threads],
    })


@app.route('/hide_chat', methods=['POST'])
def hide_chat():
    """不显示该聊天：从列表拿掉，聊天记录仍在。"""
    data = request.get_json(force=True)
    user_id = data.get('user_id')
    friend_id = data.get('friend_id')
    if not user_id or not friend_id:
        return jsonify({"success": False, "message": "参数缺失"})

    thread = ChatThread.query.filter_by(
        user_id=int(user_id), friend_id=int(friend_id)
    ).first()
    if thread is None:
        return jsonify({"success": False, "message": "聊天条目不存在"})

    thread.is_hidden = True
    db.session.commit()
    return jsonify({"success": True, "message": "已不显示该聊天"})


@app.route('/delete_chat', methods=['POST'])
def delete_chat():
    """删除聊天条目，并清空我这边能看到的历史（不影响对方）。"""
    data = request.get_json(force=True)
    user_id = data.get('user_id')
    friend_id = data.get('friend_id')
    if not user_id or not friend_id:
        return jsonify({"success": False, "message": "参数缺失"})

    user_id, friend_id = int(user_id), int(friend_id)
    thread = get_or_create_thread(user_id, friend_id)

    last = (
        Message.query.filter(pair_message_filter(user_id, friend_id))
        .order_by(Message.id.desc())
        .first()
    )
    max_id = last.id if last else 0
    thread.is_hidden = True
    thread.cleared_before_id = max_id
    thread.last_read_message_id = max_id
    db.session.commit()
    return jsonify({"success": True, "message": "已删除聊天及记录"})


@app.route('/mark_read', methods=['POST'])
def mark_read():
    """进入 ChatBox 后把该会话标为已读。"""
    data = request.get_json(force=True)
    user_id = data.get('user_id')
    friend_id = data.get('friend_id')
    if not user_id or not friend_id:
        return jsonify({"success": False, "message": "参数缺失"})

    user_id, friend_id = int(user_id), int(friend_id)
    thread = ChatThread.query.filter_by(user_id=user_id, friend_id=friend_id).first()
    if thread is None:
        return jsonify({"success": True, "message": "无需标记"})

    last = last_visible_message(thread)
    if last:
        thread.last_read_message_id = last.id
    db.session.commit()
    return jsonify({"success": True, "message": "已读"})


@socketio.on('connect')
def on_connect():
    # 此时还不知道是谁；等客户端 emit join
    emit('server_hello', {'message': 'connected'})


@socketio.on('disconnect')
def on_disconnect():
    sid = request.sid
    uid = online_users.pop(sid, None)
    if uid is not None:
        leave_room(f'user_{uid}')


@socketio.on('join')
def on_join(data):
    data = data or {}
    user_id = data.get('user_id')
    if not user_id:
        emit('error', {'message': 'join 缺少 user_id'})
        return

    user = User.query.get(user_id)
    if not user:
        emit('error', {'message': '用户不存在'})
        return

    room = f'user_{user_id}'
    join_room(room)
    online_users[request.sid] = int(user_id)
    emit('joined', {'success': True, 'user_id': int(user_id), 'message': '已上线'})


@socketio.on('leave')
def on_leave(_data):
    sid = request.sid
    uid = online_users.pop(sid, None)
    if uid is not None:
        leave_room(f'user_{uid}')


def _ws_attach(user_id, ws):
    with _ws_lock:
        bucket = _ws_clients.setdefault(int(user_id), [])
        if ws not in bucket:
            bucket.append(ws)


def _ws_detach(user_id, ws):
    if user_id is None:
        return
    with _ws_lock:
        bucket = _ws_clients.get(int(user_id))
        if not bucket or ws not in bucket:
            return
        bucket.remove(ws)
        if not bucket:
            _ws_clients.pop(int(user_id), None)


def push_ws(user_id, payload):
    raw = json.dumps(payload, ensure_ascii=False)
    with _ws_lock:
        clients = list(_ws_clients.get(int(user_id), ()))
    for client in clients:
        try:
            client.send(raw)
        except Exception:
            _ws_detach(user_id, client)


@sock.route('/ws')
def chat_ws(ws):
    """手机 WebSocketExt 走这里。文本帧是 JSON，type 为 join / joined / new_message / error。"""
    user_id = None
    try:
        while True:
            raw = ws.receive()
            if not raw:
                break
            if isinstance(raw, bytes):
                raw = raw.decode('utf-8')
            try:
                data = json.loads(raw)
            except (TypeError, ValueError):
                ws.send(json.dumps({'type': 'error', 'message': '无法解析消息'}, ensure_ascii=False))
                continue
            if data.get('type') != 'join':
                continue
            try:
                uid = int(data.get('user_id'))
            except (TypeError, ValueError):
                ws.send(json.dumps({'type': 'error', 'message': 'join 缺少 user_id'}, ensure_ascii=False))
                continue
            if User.query.get(uid) is None:
                ws.send(json.dumps({'type': 'error', 'message': '用户不存在'}, ensure_ascii=False))
                continue
            if user_id is not None and user_id != uid:
                _ws_detach(user_id, ws)
            user_id = uid
            _ws_attach(user_id, ws)
            ws.send(json.dumps({'type': 'joined', 'user_id': uid}, ensure_ascii=False))
    finally:
        _ws_detach(user_id, ws)


def deliver_private_message(from_id, to_id, content):
    """保存一条私聊并推给双方房间。成功时返回消息字典，失败时返回错误文字。"""
    if from_id == to_id:
        return None, '不能给自己发消息'
    if not User.query.get(from_id) or not User.query.get(to_id):
        return None, '对方用户不存在'
    if not are_friends(from_id, to_id):
        return None, '你们还不是好友，无法发消息'

    msg = Message(from_id=from_id, to_id=to_id, content=content[:2000])
    db.session.add(msg)
    db.session.flush()

    now = datetime.utcnow()
    sender_thread = get_or_create_thread(from_id, to_id)
    sender_thread.is_hidden = False
    sender_thread.updated_at = now
    sender_thread.last_read_message_id = msg.id

    receiver_thread = get_or_create_thread(to_id, from_id)
    receiver_thread.is_hidden = False  # 新消息让会话重新出现在对方 ChatList
    receiver_thread.updated_at = now

    db.session.commit()
    payload = message_to_dict(msg)
    socketio.emit('new_message', payload, room=f'user_{from_id}')
    if to_id != from_id:
        socketio.emit('new_message', payload, room=f'user_{to_id}')
    notice = dict(payload)
    notice['type'] = 'new_message'
    push_ws(from_id, notice)
    if to_id != from_id:
        push_ws(to_id, notice)
    return payload, None


@app.route('/send_message', methods=['POST'])
def send_message():
    # 绕开 App Inventor 默认的 text/plain
    data = request.get_json(force=True) or {}
    content = (data.get('content') or '').strip()
    try:
        from_id = int(data.get('from_id'))
        to_id = int(data.get('to_id'))
    except (TypeError, ValueError):
        return jsonify({"success": False, "message": "消息参数不完整"})
    if not content:
        return jsonify({"success": False, "message": "消息参数不完整"})
    payload, error = deliver_private_message(from_id, to_id, content)
    if error:
        return jsonify({"success": False, "message": error})
    return jsonify({"success": True, "message": "已发送", "id": payload['id']})


@socketio.on('send_private')
def on_send_private(data):
    data = data or {}
    from_id = data.get('from_id')
    to_id = data.get('to_id')
    content = (data.get('content') or '').strip()

    if not from_id or not to_id or not content:
        emit('error', {'message': '消息参数不完整'})
        return

    from_id, to_id = int(from_id), int(to_id)

    # 防止伪造：连接时 join 登记的人，必须和 from_id 一致
    bound = online_users.get(request.sid)
    if bound is not None and bound != from_id:
        emit('error', {'message': '身份不匹配'})
        return

    _payload, error = deliver_private_message(from_id, to_id, content)
    if error:
        emit('error', {'message': error})


if __name__ == '__main__':
    socketio.run(
        app,
        host='0.0.0.0',
        port=5000,
        debug=True,
        use_reloader=False,
    )
