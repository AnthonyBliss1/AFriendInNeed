import sys
import queue
import os
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QLabel
from PySide6.QtCore import QTimer, Signal, QObject, Qt, QPoint
from PySide6.QtGui import QPixmap

class PokerGUI(QWidget):
    update_signal = Signal(object)

    def __init__(self, gui_queue):
        super().__init__()
        self.gui_queue = gui_queue
        self.uuid_to_player_name = {}  
        self.player_hole_cards = {}    
        self.current_seats = [] 

        self.player_colors = {
            '4o': '#FF6B6B',
            'Opus': '#4ECB71',
            'Sonnet': '#4DA6FF',
        }

        self.card_back = QPixmap('assets/card_back.png')
        self.card_width = self.card_back.width()
        self.card_height = self.card_back.height()

        self.init_ui()

        self.update_signal.connect(self.update_game_state)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.process_gui_queue)
        self.timer.start(100)

    def init_ui(self):
        self.layout = QVBoxLayout()

        self.table_label = QLabel(self)
        table_image = QPixmap('assets/table.png')
        self.table_label.setPixmap(table_image)
        self.table_label.setScaledContents(True)
        self.table_label.setGeometry(0, 0, table_image.width(), table_image.height())

        self.table_width = table_image.width()
        self.table_height = table_image.height()

        self.setFixedSize(self.table_width, self.table_height)

        self.init_players()
        self.init_community_cards()

        self.init_chat_and_actions()

        self.setLayout(self.layout)

    def init_players(self):
        self.player_card_labels = {}
        self.player_name_labels = {}
        self.player_chip_labels = {}

        # Define positions for each player (unchanged)
        self.player_positions = {
            '4o': QPoint(self.table_width // 2 - self.card_width, self.table_height - (self.card_height + 50)),
            'Opus': QPoint(self.table_width - (self.card_width * 2 + 50), self.table_height // 2 - self.card_height // 2),
            'Sonnet': QPoint(self.table_width // 2 - self.card_width, 50),
        }

        for player_name, position in self.player_positions.items():
            card_label1 = QLabel(self)
            card_label2 = QLabel(self)

            card_label1.setPixmap(self.card_back)
            card_label2.setPixmap(self.card_back)
            card_label1.setFixedSize(self.card_width, self.card_height)
            card_label2.setFixedSize(self.card_width, self.card_height)

            card_label1.move(position.x(), position.y())
            card_label2.move(position.x() + self.card_width + 10, position.y())

            self.player_card_labels[player_name] = (card_label1, card_label2)

            # Calculate the center position for the name label
            name_label_width = self.card_width * 2 + 10  # Width of two cards plus spacing
            name_label_x = position.x() + (name_label_width - self.card_width * 2) // 2

            # Create the player's name label
            name_label = QLabel(player_name, self)
            name_label.setStyleSheet("color: white; font-weight: bold;")
            name_label.setAlignment(Qt.AlignCenter)
            name_label.setFixedWidth(name_label_width)

            chip_label = QLabel("Chips: 1000", self)
            chip_label.setStyleSheet("color: white;")
            chip_label.setAlignment(Qt.AlignCenter)
            chip_label.setFixedWidth(name_label_width)

            # Position labels based on player
            if player_name == 'Sonnet':
                name_label.move(name_label_x, position.y() - 55)
                chip_label.move(name_label_x, position.y() - 35)
            else:  # '4o' and 'Opus'
                name_label.move(name_label_x, position.y() + self.card_height + 5)
                chip_label.move(name_label_x, position.y() + self.card_height + 25)

            self.player_name_labels[player_name] = name_label
            self.player_chip_labels[player_name] = chip_label

    def init_community_cards(self):
        self.community_card_labels = []

        total_community_width = 5 * self.card_width + 4 * 10
        start_x = (self.table_width - total_community_width) // 2
        start_y = (self.table_height - self.card_height) // 2

        for i in range(5):
            card_label = QLabel(self)

            card_label.setPixmap(self.card_back)
            card_label.setFixedSize(self.card_width, self.card_height)

            card_label.move(start_x + i * (self.card_width + 10), start_y)

            self.community_card_labels.append(card_label)

    def init_chat_and_actions(self):
        # Initialize game state display (actions)
        self.game_state_display = QTextEdit(self)
        self.game_state_display.setReadOnly(True)
        self.game_state_display.setStyleSheet("""
            background-color: rgba(0, 0, 0, 150);
            color: white;
            font-size: 14px;
        """)
        self.game_state_display.setGeometry(10, 10, 250, 100)
        self.game_state_display.raise_()

        # Initialize chat box
        self.chat_box = QTextEdit(self)
        self.chat_box.setReadOnly(True)
        self.chat_box.setStyleSheet("""
            background-color: rgba(0, 0, 0, 150);
            color: white;
            font-size: 11px;
        """)
        self.chat_box.setGeometry(10, self.height() - 120, 300, 100)
        self.chat_box.raise_()

    def process_gui_queue(self):
        while not self.gui_queue.empty():
            queue_item = self.gui_queue.get()
            message_type = queue_item[0]
            if message_type == 'game_state':
                data = queue_item[1]
                self.update_signal.emit(data)
            elif message_type == 'player_hole_cards':
                data = queue_item[1]
                player_uuid = data.get('player_uuid')
                hole_card = data.get('hole_card', [])
                self.player_hole_cards[player_uuid] = hole_card
                # Update player info
                seat = next((seat for seat in self.current_seats if str(seat.get('uuid', '')) == player_uuid), None)
                if seat:
                    self.update_player_info(seat, hole_cards=hole_card)
            elif message_type == 'chat':
                sender_name = queue_item[1]
                message = queue_item[2]
                self.display_chat_message(sender_name, message)
            elif message_type == 'update_uuid_mapping':
                data = queue_item[1]
                uuid = data.get('uuid')
                display_name = data.get('display_name')
                self.uuid_to_player_name[uuid] = display_name
            else:
                print(f"Unknown message type: {message_type}")

    def update_game_state(self, message):
        event = message.get('event', '')
        print(f"Update Game State Called with event: {event}")

        if event == 'game_start':
            self.handle_game_start(message)
        elif event == 'round_start':
            self.handle_round_start(message)
        elif event == 'street_start':
            self.handle_street_start(message)
        elif event == 'game_update':
            self.handle_game_update(message)
        elif event == 'round_result':
            self.handle_round_result(message)
        else:
            print(f"Unknown event type: {event}")

    # Event handlers
    def handle_game_start(self, message):
        game_info = message.get('game_info', {})
        self.game_state_display.append("Game started.")
        self.display_community_cards([])


    def handle_round_start(self, message):
        print("Handling round start")
        round_count = message.get('round_count', 0)
        seats = message.get('seats', [])
        self.current_seats = seats

        self.game_state_display.append(f"Round {round_count} started.")

        # Clear community cards for the new round
        self.display_community_cards([])

        # Update player info
        for seat in seats:
            seat_uuid = str(seat.get('uuid', ''))
            seat_hole_cards = self.player_hole_cards.get(seat_uuid, [])
            self.update_player_info(seat, hole_cards=seat_hole_cards)

    def handle_street_start(self, message):
        street = message.get('street', '')
        round_state = message.get('round_state', {})
        self.game_state_display.append(f"Street {street} started.")

        # Update community cards
        community_cards = round_state.get('community_card', [])
        self.display_community_cards(community_cards)

    def handle_game_update(self, message):
        action = message.get('action', {})
        player_uuid = str(action.get('player_uuid', ''))
        player_name = self.uuid_to_player_name.get(player_uuid, 'Unknown')
        action_type = action.get('action', '')
        amount = action.get('amount', 0)
        self.game_state_display.append(f"{player_name}: {action_type} ({amount})")

        if action_type == 'fold':
            # Find the seat for the player who folded
            folded_seat = next((seat for seat in self.current_seats if str(seat.get('uuid', '')) == player_uuid), None)
            if folded_seat:
                # Update the player info with folded state
                self.update_player_info(folded_seat, folded=True)

    def handle_round_result(self, message):
        winners = message.get('winners', [])
        winner_names = []
        for winner in winners:
            winner_uuid = str(winner.get('uuid', ''))
            winner_name = self.uuid_to_player_name.get(winner_uuid, 'Unknown')
            winner_names.append(winner_name)
        self.game_state_display.append(f"Round ended. Winners: {', '.join(winner_names)}")

        # Clear hole cards for all players
        for player_name, card_labels in self.player_card_labels.items():
            card_back = QPixmap('assets/card_back.png')
            for label in card_labels:
                label.setPixmap(card_back)

        # Clear community cards
        self.display_community_cards([])

    def display_community_cards(self, community_cards):
        for i, card_label in enumerate(self.community_card_labels):
            if i < len(community_cards):
                card_image_path = f"assets/deck/{community_cards[i]}.png"
                if os.path.exists(card_image_path):
                    card_image = QPixmap(card_image_path)
                    card_label.setPixmap(card_image)
                    card_label.setFixedSize(card_image.width(), card_image.height())
                else:
                    card_label.clear()
            else:
                # Show card back for unrevealed cards
                card_label.setPixmap(self.card_back)
                card_label.setFixedSize(self.card_width, self.card_height)

    def update_player_info(self, seat, hole_cards=None, folded=False):
        player_uuid = str(seat.get('uuid', ''))
        player_name = self.uuid_to_player_name.get(player_uuid, 'Unknown')

        # Update card labels
        card_labels = self.player_card_labels.get(player_name)
        if card_labels:
            if folded:
                # Use the folded card back image
                folded_card_back = QPixmap('assets/card_back_fold.png')
                for label in card_labels:
                    label.setPixmap(folded_card_back)
                    label.setFixedSize(folded_card_back.width(), folded_card_back.height())
            elif hole_cards:
                for i, card in enumerate(hole_cards):
                    card_image_path = f"assets/deck/{card}.png"
                    if os.path.exists(card_image_path):
                        card_image = QPixmap(card_image_path)
                        card_labels[i].setPixmap(card_image)
                        card_labels[i].setFixedSize(card_image.width(), card_image.height())
                    else:
                        card_labels[i].clear()
            else:
                # Use the regular card back image
                for label in card_labels:
                    label.setPixmap(self.card_back)
                    label.setFixedSize(self.card_width, self.card_height)

        # Update chip amount
        chip_label = self.player_chip_labels.get(player_name)
        if chip_label:
            stack = seat.get('stack', 0)
            chip_label.setText(f"Chips: {stack}")

    def display_chat_message(self, sender_name, message):
        if message is None or message == "":
            return

        if isinstance(message, str):
            text = message
        elif isinstance(message, list) and message and hasattr(message[0], 'text'):
            text = message[0].text
        else:
            text = str(message)

        # Remove any newline characters and extra whitespace
        text = ' '.join(text.split())

        color = self.player_colors.get(sender_name, 'black')

        formatted_message = f'<span style="color: {color};">{sender_name}: {text}</span>'

        self.chat_box.append(formatted_message)
        self.chat_box.append("")

        self.chat_box.verticalScrollBar().setValue(
            self.chat_box.verticalScrollBar().maximum()
        )