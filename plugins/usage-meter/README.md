# Usage Meter

One line above the chat: how full this chat is, how much of your 5-hour and weekly limits is used (with the 5-hour reset time on your own clock), and whether the chat is still warm. Claude keeps a chat in short-term memory for about an hour after its last reply. After that, the next message makes it reread the whole chat.

When a chat has gone cold and holds a lot, the meter holds your message before it sends and shows a card with the numbers: Send anyway, Start fresh (runs /handoff when that mod is installed) or Cancel (puts your text back). Scheduled tasks and messages starting with "go:" are never held.

`/keepwarm` (or `/keepwarm on|off`) keeps this chat warm while you are away: 8 minutes before the cache would expire it re-reads the chat from cache in the background, adding nothing to the chat. The warm part then reads `warm 41m left, ping 15:52 (2)`, the number being pings since your last turn. Each ping costs a cache read of the whole chat (about a tenth of the rewrite it saves). Keep-warm stops itself after 20 pings with no turn between, when a ping finds the cache already cold, on an API error that will not clear, and after an app restart until the chat has replied once. It is off in every new session. Everything else only reads numbers Claude already has, so it costs nothing.
