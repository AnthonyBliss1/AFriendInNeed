from pypokerengine.players import BasePokerPlayer
import random
import uuid
import os
from dotenv import load_dotenv
import time
import anthropic
from openai import OpenAI
from poker_game import broadcast_chat_message, gui_queue, uuid_to_player_name

load_dotenv()

class ModelPokerAgent(BasePokerPlayer):
    def __init__(self, model_name, personality_description, display_name):
        super().__init__()
        self.model_name = model_name
        self.personality_description = personality_description
        self.memory = []
        self.display_name = display_name
        self.chat_history = []
        self.action_delay = 7  # Add a delay before taking action
        self.game_memory = []

    def declare_action(self, valid_actions, hole_card, round_state):
        self.update_memory(hole_card, round_state)
        time.sleep(self.action_delay)

        action, amount = self.get_action_from_model(valid_actions, hole_card, round_state)

        self.game_memory.append({
            'action': action,
            'amount': amount,
            'state': round_state,
            'hole_card': hole_card
        })

        self.consider_chatting_or_responding(round_state, action, amount)

        return action, amount

    def update_memory(self, hole_card, round_state):
        self.memory.append({
            'hole_card': hole_card,
            'round_state': round_state,
        })

    def decide_to_chat(self, round_state):
        if round_state['street'] in ['preflop', 'flop', 'turn', 'river']:
            return True
        return random.random() < 0.3  # 30% chance to chat at other times

    def send_chat_message(self, round_state, action, amount):
        prompt = self.create_chat_prompt(round_state, action, amount)
        message = self.get_chat_response(prompt, round_state)
        self.chat_history.append(f"{self.display_name}: {message}")

        return message

    def create_chat_prompt(self, round_state, action, amount):
        action_str = f"{action}:{amount}" if action == "raise" else action
        prompt = f"""
{self.personality_description}
You are playing Texas Hold'em poker.
Current round state: {round_state}
Recent chat history:
{self.get_recent_chat_history()}

Based on your personality and the current game state, generate a short chat message (1-2 sentences) to engage with the other players. 
Talk to them and respond to their chat. Refer to them by name.
"""
        return prompt.strip()

    def get_chat_response(self, prompt, round_state):
        raise NotImplementedError("Subclasses must implement get_chat_response")

    def get_action_from_model(self, valid_actions, hole_card, round_state):
        
        pass

    def summarize_memory(self):
        recent_memory = self.memory[-5:]  # last 5 entries
        summary = []
        for entry in recent_memory:
            hole_cards = entry['hole_card']
            round_street = entry['round_state']['street']
            summary.append(f"Hand: {hole_cards}, Round: {round_street}")
        return '; '.join(summary)

    def get_recent_chat_history(self):
        return "\n".join(self.chat_history[-5:])

    def summarize_game_memory(self):
        recent_memory = self.game_memory[-5:]
        summary = []
        for entry in recent_memory:
            summary.append(f"Action: {entry['action']}, Result: {'win' if entry.get('win', False) else 'loss'}")
        return '; '.join(summary)

    def receive_game_start_message(self, game_info):
        print(f"{self.display_name}: receive_game_start_message called")

    def receive_round_start_message(self, round_count, hole_card, seats):
        print(f"{self.display_name}: receive_round_start_message called")
        gui_queue.put(('player_hole_cards', {
            'player_uuid': str(self.uuid),
            'hole_card': hole_card
        }))

    def receive_street_start_message(self, street, round_state):
        print(f"{self.display_name}: receive_street_start_message called")

    def receive_game_update_message(self, action, round_state):
        print(f"{self.display_name}: receive_game_update_message called")
        message = self.consider_chatting_or_responding(round_state, last_action=action)
        if message:
            broadcast_chat_message(self.display_name, message)

    def receive_round_result_message(self, winners, hand_info, round_state):
        print(f"{self.display_name}: receive_round_result_message called")
        if self.game_memory:
            last_action = self.game_memory[-1]
            last_action['win'] = any(winner['uuid'] == self.uuid for winner in winners)

    def set_uuid(self, uuid):
        super().set_uuid(uuid)
        self.uuid = uuid
        uuid_to_player_name[str(self.uuid)] = self.display_name
        print(f"{self.display_name} assigned UUID: {self.uuid}")

        gui_queue.put(('update_uuid_mapping', {
            'uuid': str(self.uuid),
            'display_name': self.display_name
        }))

    def consider_chatting_or_responding(self, round_state, action=None, amount=None, last_action=None):
        chat_chance = 0.2  # 20% base chance to chat

        if action:
            chat_chance += 0.1 
        if last_action:
            chat_chance += 0.2  

        if random.random() < chat_chance:
            prompt = self.create_chat_prompt(round_state, action, amount, last_action)
            message = self.get_chat_response(prompt, round_state)
            if message.strip():
                self.chat_history.append(f"{self.display_name}: {message}")
                return message
        return None

    def create_chat_prompt(self, round_state, action, amount, last_action):
        action_str = f"{action}:{amount}" if action == "raise" else action
        
        if isinstance(last_action, dict):
            player = last_action.get('player', 'Unknown')
            action_type = last_action.get('action', 'Unknown')
            last_action_str = f"{player} {action_type}"
        elif last_action:
            last_action_str = str(last_action)
        else:
            last_action_str = "None"
        
        prompt = f"""
{self.personality_description}
You are playing Texas Hold'em poker.
Current round state: {round_state}
Your last action: {action_str}
Last action by another player: {last_action_str}
Recent chat history:
{self.get_recent_chat_history()}

Based on your personality, the current game state, and recent actions, generate a short chat message (1-2 sentences) to engage with the other players. 
You can comment on the game, respond to others, or just chat. Be natural and stay in character.
If you don't think it's appropriate to chat right now, respond with an empty string.
"""
        return prompt.strip()


# gpt-4o
class GPT4PokerAgent(ModelPokerAgent):
    def __init__(self, model_name, personality_description, display_name):
        super().__init__(model_name, personality_description, display_name)
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.is_event_handler = True  # Flag to identify this agent as the event handler

    def get_chat_response(self, prompt, round_state):
        completion = self.client.chat.completions.create(
            model=self.model_name,
            messages=[
                {"role": "system", "content": f"{self.personality_description} Respond with a brief message (1-2 sentences max)."},
                {"role": "user", "content": f"Game state: {round_state}\n\n{prompt}"}
            ],
            max_tokens=50
        )
        return completion.choices[0].message.content.strip()

    def get_action_from_model(self, valid_actions, hole_card, round_state):
        prompt = self.create_action_prompt(valid_actions, hole_card, round_state)
        completion = self.client.chat.completions.create(
            model=self.model_name,
            messages=[
                {"role": "system", "content": self.personality_description},
                {"role": "user", "content": prompt}
            ],
            max_tokens=50
        )
        action = self.parse_action_response(completion.choices[0].message.content, valid_actions)
        return action

    def create_action_prompt(self, valid_actions, hole_card, round_state):
        memory_summary = self.summarize_memory()
        chat_history = self.get_recent_chat_history()
        game_memory = self.summarize_game_memory()
        prompt = f"""
{self.personality_description}
You are playing Texas Hold'em poker.
Your hand: {hole_card}
Community cards: {round_state['community_card']}
Valid actions: {[action['action'] for action in valid_actions]}
Past experiences: {memory_summary}
Recent chat:
{chat_history}
Past game decisions and outcomes: {game_memory}

Based on your personality, past experiences, chat history, and the game state, what action will you take?
Respond with one of the valid actions and an amount if necessary.
"""
        return prompt.strip()

    def parse_action_response(self, response_text, valid_actions):
        response_text = response_text.lower()
        for action in valid_actions:
            action_name = action['action']
            if action_name in response_text:
                amount = action.get('amount', 0)
                if action_name == 'raise':
                    amount = self.extract_raise_amount(response_text, action)
                return action_name, amount
        return valid_actions[0]['action'], valid_actions[0].get('amount', 0)

    def extract_raise_amount(self, response_text, action):
        import re
        amounts = re.findall(r'\b\d+\b', response_text)
        amount_info = action['amount']
        if amounts:
            amount = int(amounts[0])
            if isinstance(amount_info, dict):
                min_amount = amount_info['min']
                max_amount = amount_info['max']
                if min_amount <= amount <= max_amount:
                    return amount
                else:
                    return min_amount
            else:
                return amount_info
        else:
            if isinstance(amount_info, dict):
                return amount_info['min']
            else:
                return amount_info

    def receive_game_start_message(self, game_info):
        super().receive_game_start_message(game_info)
        if self.is_event_handler:
            gui_queue.put(('game_state', {
                'event': 'game_start',
                'game_info': game_info
            }))

    def receive_round_start_message(self, round_count, hole_card, seats):
        super().receive_round_start_message(round_count, hole_card, seats)
        if self.is_event_handler:
            gui_queue.put(('game_state', {
                'event': 'round_start',
                'round_count': round_count,
                'seats': seats
            }))

    def receive_street_start_message(self, street, round_state):
        super().receive_street_start_message(street, round_state)
        if self.is_event_handler:
            gui_queue.put(('game_state', {
                'event': 'street_start',
                'street': street,
                'round_state': round_state
            }))

    def receive_game_update_message(self, action, round_state):
        super().receive_game_update_message(action, round_state)
        if self.is_event_handler:
            gui_queue.put(('game_state', {
                'event': 'game_update',
                'action': action,
                'round_state': round_state
            }))

    def receive_round_result_message(self, winners, hand_info, round_state):
        super().receive_round_result_message(winners, hand_info, round_state)
        if self.is_event_handler:
            gui_queue.put(('game_state', {
                'event': 'round_result',
                'winners': winners,
                'hand_info': hand_info,
                'round_state': round_state
            }))


# claude opus
class ClaudePokerAgent(ModelPokerAgent):
    def get_chat_response(self, prompt, round_state):
        response = self.call_claude_api(prompt, round_state, model=self.model_name)
        return response.content[0].text if response.content else ""

    def get_action_from_model(self, valid_actions, hole_card, round_state):
        prompt = self.create_action_prompt(valid_actions, hole_card, round_state)
        response = self.call_claude_api(prompt, round_state, model=self.model_name)
        response_text = response.content[0].text if response.content else ""
        action = self.parse_action_response(response_text, valid_actions)
        return action

    def call_claude_api(self, prompt, round_state, model):
        anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")

        client = anthropic.Anthropic(api_key=anthropic_api_key)

        response = client.messages.create(
            model=model,
            max_tokens=50,
            system=f"{self.personality_description}. You just took an action in the game. Respond with a brief message (1-2 sentences max) that is consistent with your action.",
            messages=[
                {"role": "user", "content": f"Game state: {round_state}\n\n{prompt}"}
            ]
        )

        return response

    def parse_action_response(self, response_text, valid_actions):
        response_text = response_text.lower()
        for action in valid_actions:
            action_name = action['action']
            if action_name in response_text:
                amount = action.get('amount', 0)
                if action_name == 'raise':
                    amount = self.extract_raise_amount(response_text, action)
                return action_name, amount
        return valid_actions[0]['action'], valid_actions[0].get('amount', 0)

    def extract_raise_amount(self, response_text, action):
        import re
        amounts = re.findall(r'\b\d+\b', response_text)
        amount_info = action['amount']
        if amounts:
            amount = int(amounts[0])
            if isinstance(amount_info, dict):
                min_amount = amount_info['min']
                max_amount = amount_info['max']
                if min_amount <= amount <= max_amount:
                    return amount
                else:
                    return min_amount
            else:
                return amount_info
        else:
            if isinstance(amount_info, dict):
                return amount_info['min']
            else:
                return amount_info

    def create_action_prompt(self, valid_actions, hole_card, round_state):
        memory_summary = self.summarize_memory()
        chat_history = self.get_recent_chat_history()
        game_memory = self.summarize_game_memory()
        prompt = f"""
{self.personality_description}
You are playing Texas Hold'em poker.
Your hand: {hole_card}
Community cards: {round_state['community_card']}
Valid actions: {[action['action'] for action in valid_actions]}
Past experiences: {memory_summary}
Recent chat:
{chat_history}
Past game decisions and outcomes: {game_memory}

Based on your personality, past experiences, chat history, and the game state, what action will you take?
Respond with one of the valid actions and an amount if necessary.
"""
        return prompt.strip()


# claude sonnet 3.5
class ClaudeSonnet35PokerAgent(ModelPokerAgent):
    def get_chat_response(self, prompt, round_state):
        response = self.call_claude_api(prompt, round_state, model=self.model_name)
        return response.content[0].text if response.content else ""

    def get_action_from_model(self, valid_actions, hole_card, round_state):
        prompt = self.create_action_prompt(valid_actions, hole_card, round_state)
        response = self.call_claude_api(prompt, round_state, model=self.model_name)
        response_text = response.content[0].text if response.content else ""
        action = self.parse_action_response(response_text, valid_actions)
        return action

    def call_claude_api(self, prompt, round_state, model):
        anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")

        client = anthropic.Anthropic(api_key=anthropic_api_key)

        response = client.messages.create(
            model=model,
            max_tokens=50,
            system=f"{self.personality_description}. You just took an action in the game. Respond with a brief message (1-2 sentences max) that is consistent with your action.",
            messages=[
                {"role": "user", "content": f"Game state: {round_state}\n\n{prompt}"}
            ]
        )

        return response

    def parse_action_response(self, response_text, valid_actions):
        response_text = response_text.lower()
        for action in valid_actions:
            action_name = action['action']
            if action_name in response_text:
                amount = action.get('amount', 0)
                if action_name == 'raise':
                    amount = self.extract_raise_amount(response_text, action)
                return action_name, amount
        return valid_actions[0]['action'], valid_actions[0].get('amount', 0)

    def extract_raise_amount(self, response_text, action):
        import re
        amounts = re.findall(r'\b\d+\b', response_text)
        amount_info = action['amount']
        if amounts:
            amount = int(amounts[0])
            if isinstance(amount_info, dict):
                min_amount = amount_info['min']
                max_amount = amount_info['max']
                if min_amount <= amount <= max_amount:
                    return amount
                else:
                    return min_amount
            else:
                return amount_info
        else:
            if isinstance(amount_info, dict):
                return amount_info['min']
            else:
                return amount_info

    def create_action_prompt(self, valid_actions, hole_card, round_state):
        memory_summary = self.summarize_memory()
        chat_history = self.get_recent_chat_history()
        game_memory = self.summarize_game_memory()
        prompt = f"""
{self.personality_description}
You are playing Texas Hold'em poker.
Your hand: {hole_card}
Community cards: {round_state['community_card']}
Valid actions: {[action['action'] for action in valid_actions]}
Past experiences: {memory_summary}
Recent chat:
{chat_history}
Past game decisions and outcomes: {game_memory}

Based on your personality, past experiences, chat history, and the game state, what action will you take?
Respond with one of the valid actions and an amount if necessary.
"""
        return prompt.strip()