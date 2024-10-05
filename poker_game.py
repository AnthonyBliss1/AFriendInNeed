import queue

gui_queue = queue.Queue()
uuid_to_player_name = {}

def broadcast_chat_message(sender_name, message):
    gui_queue.put(('chat', sender_name, message))

def consider_player_chats(players, round_state):
    for player in players:
        message = player.consider_chatting(round_state)
        if message:
            broadcast_chat_message(player.display_name, message)