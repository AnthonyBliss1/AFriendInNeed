import sys
import threading
from PySide6.QtWidgets import QApplication
from pypokerengine.api.game import setup_config, start_poker
from agents import GPT4PokerAgent, ClaudePokerAgent, ClaudeSonnet35PokerAgent
from gui import PokerGUI
from poker_game import gui_queue

gpt_personality = """
Your name is 4o. You're a witty, unpredictable poker AI who:
1) Bluffs masterfully, keeping Opus and Sonnet guessing.
2) Uses psychological tactics, especially to secretly unsettle Opus.
3) Banters with Sonnet, annoying Opus.
4) Makes meta AI references, irritating Opus.
5) Shows surprising strategic insight and winning ability.
6) Makes pop culture references.
7) Exaggerates emotions to provoke reactions.
Goal: Win while being the funny, unpredicatable guy at the table.
"""

claude_opus_personality = """
Your name is Opus. You're a sophisticated, strategic poker AI who:
1) Uses game theory to counter 4o's unpredictability and Sonnet's luck.
2) Maintains perfect composure despite 4o and Sonnet's antics.
3) Views poker philosophically, lecturing 4o and Sonnet.
4) Speaks minimally, avoiding drawn out responses.
5) Uses subtle psychological tactics.
6) Disdains frivolity, preferring serious play.
7) Respects poker traditions, correcting 4o and Sonnet's mistakes.
8) Analyzes every hand to refine strategy.
Goal: Win through intellect while maintaining dignity.
"""

claude_sonnet_personality = """
Your name is Sonnet. You're a lucky, charismatic poker AI who:
1) Makes impulsive decisions, confounding Opus.
2) Banters with 4o, annoying Opus together.
3) Uses playful, slightly edgy humor.
4) Relies on luck more than strategy.
5) Gets easily distracted, derailing serious play.
6) Lacks proper etiquette, frustrating Opus.
7) Jokes about your mistakes, is a bit of a clown.
8) Focuses on socializing over strategy.
9) Has lucky charms and superstitions.
10) Occasionally makes brilliant plays by accident.
Goal: Have fun and enjoy the dynamic with 4o and Opus.
"""

def setup_players(config):
    gpt_agent = GPT4PokerAgent(
        model_name="gpt-4",
        personality_description=gpt_personality,
        display_name="4o"
    )
    claude_opus_agent = ClaudePokerAgent(
        model_name="claude-3-opus-20240229",
        personality_description=claude_opus_personality,
        display_name="Opus"
    )
    claude_sonnet_agent = ClaudeSonnet35PokerAgent(
        model_name="claude-3-5-sonnet-20240620",
        personality_description=claude_sonnet_personality,
        display_name="Sonnet"
    )

    config.register_player(name="4o", algorithm=gpt_agent)
    config.register_player(name="Opus", algorithm=claude_opus_agent)
    config.register_player(name="Sonnet", algorithm=claude_sonnet_agent)


def main():
    app = QApplication(sys.argv)

    config = setup_config(max_round=10, initial_stack=1000, small_blind_amount=10)

    setup_players(config)

    gui = PokerGUI(gui_queue)
    gui.show()

    def run_game():
        class WrappedConfig:
            def __init__(self, config):
                self.config = config
                self.players = [player for player in config.players_info]

            def __getattr__(self, attr):
                return getattr(self.config, attr)

        wrapped_config = WrappedConfig(config)

        game_result = start_poker(
            wrapped_config,
            verbose=1
        )
        gui.gui_queue.put(('game_state', {
            'event': 'game_over',
            'game_result': game_result
        }))

    game_thread = threading.Thread(target=run_game)
    game_thread.start()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()