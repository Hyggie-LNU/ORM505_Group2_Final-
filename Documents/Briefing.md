# Briefing —— Replica of QQ
## Key word of the app

- **Register**
- **Log in**
- **Add Friend**
- **Real-time Chatting**
- **Client-Server Framework**
## CLIENT: Planned features & Screens

- Register and log in (Register, Login)
- Create a HomePage to manage screen-switching rules (HomePage)
- Search by username and send a friend request (AddFriend)
- Accept or reject a friend request (FriendRequest)
- View the friend list (FriendList)
- Open a chat from a friend (FriendList->ChatBox)
- View the chat list (ChatList)
- Send and receive messages in real time (ChatBox&ChatList)

## Screen-switching Rules

Register, login, and logout.

```mermaid
%%{init: {"theme": "neutral", "flowchart": {"curve": "basis", "nodeSpacing": 24, "rankSpacing": 48, "padding": 6}, "themeVariables": {"fontSize": "15px"}}}%%
flowchart LR
    Register -->|Register| Login
    Login -->|Back| Register
    Login -->|Login| HomePage
    HomePage -->|Logout| Login
```



Where HomePage can go. AddFriend, FriendRequest, FriendList, and ChatList each go back to HomePage with Back Home.

```mermaid
%%{init: {"theme": "neutral", "flowchart": {"curve": "basis", "nodeSpacing": 22, "rankSpacing": 70, "padding": 6}, "themeVariables": {"fontSize": "15px"}}}%%
flowchart LR
    HomePage -->|Search Friend & Add| AddFriend
    HomePage -->|Accept or Reject<br/>FriendRequests| FriendRequest
    HomePage -->|Check FriendList| FriendList
    HomePage -->|Messages| ChatList
```



How a chat opens. ChatBox goes back to ChatList, not to HomePage.

```mermaid
%%{init: {"theme": "neutral", "flowchart": {"curve": "basis", "nodeSpacing": 28, "rankSpacing": 56, "padding": 6}, "themeVariables": {"fontSize": "15px"}}}%%
flowchart LR
    FriendList -->|Start chat| ChatBox
    ChatList -->|Open a chat| ChatBox
    ChatBox -->|Back| ChatList
```
## SERVER: What does the backend do?

While our mobile phones are running our final app,
there must be a computer running the backend at the same time

**BACKEND IS:** 
the computer program to manage **HTTP** requests sent from the clients
update changes into project database
Also it build and maintain a **SOCKET** channel to make the chats of clients convenient


