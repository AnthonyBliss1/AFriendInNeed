import queue

gui_queue = queue.Queue()
uuid_to_player_name = {}

def broadcast_chat_message(sender_name, message):
    gui_queue.put(('chat', sender_name, message))