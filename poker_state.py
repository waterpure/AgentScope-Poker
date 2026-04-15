# -*- coding: utf-8 -*-
"""物理引擎与全局状态维护"""
import random
from typing import List, Dict, Optional
from poker_config import  generate_poker_deck
import secrets

class PlayerState:
    def __init__(self, name: str):
        self.name = name

        self.is_in_game = True  # 是否仍在游戏中（未离开或者被淘汰）
        self.hand_cards: List[Dict] = []
        self.is_have_money = True
        self.money = 200  # 初始资金
        self.money_indesk = 0  # 记录已经下注的金额
        self.money_indesk_cur = 0
        self.all_in= False

        self.personality_profile: str = "" # 用于持久化存储生成的性格准则   
    def get_hand_str(self) -> str:
        # 在牌名前面拼上花色和点数
        return ", ".join([f"{c['name']}" for c in self.hand_cards])
        
class GameEngine:
    def __init__(self, player_names: List[str], roles: List[str]):
        self.deck = generate_poker_deck()

        secure_rng = secrets.SystemRandom()
        secure_rng.shuffle(self.deck)
        self.discard_pile = []
        self.community_cards: List[Dict] = []  # [核心新增]：用来存放在桌子中央的公共牌
        self.players: Dict[str, PlayerState] = {}
        for name in player_names:
            self.players[name] = PlayerState(name)

        #初始化系统玩家（用于管理全局底池和最高下注额等公共状态）
        self.players["system"] = PlayerState(name="system")
        self.players["system"].is_in_game = False  # 系统不参与下注发言
        self.players["system"].money_indesk = 0
        self.players["system"].money = 0          
    def draw_cards(self, player_name: str, count: int) -> List[Dict]:
        """发牌逻辑：牌堆空了则洗弃牌堆"""
        drawn = []
        for _ in range(count):
            if not self.deck:
                self.deck = self.discard_pile
                self.discard_pile = []
                random.shuffle(self.deck)
                if not self.deck: 
                    break
            drawn.append(self.deck.pop(0))
            
        self.players[player_name].hand_cards.extend(drawn)
        return drawn
    def reset_game(self, player_name):
        self.players[player_name].is_in_game = True
        self.players[player_name].money_indesk = 0
        self.players[player_name].hand_cards = []
        self.players[player_name].all_in = False
    def get_public_state(self) -> str:
        """获取全场公开信息（德扑视角）"""
        state_strs = []

        system_node = self.players.get("system")
        if system_node:
            pot_size = system_node.money
            current_highest_bet = system_node.money_indesk_cur
            state_strs.append(f"💰 【桌面全局】总底池(Pot): {pot_size} | 当前最高下注额: {current_highest_bet}")
        else:
            state_strs.append("💰 【桌面全局】总底池(Pot): 0 | 当前最高下注额: 0")

        # 2. 提取各个玩家的公开筹码状态
        player_strs = []
        for name, p in self.players.items():

            if not p.is_in_game:
                player_strs.append(f"[{name}] (已弃牌)")
                continue

            player_strs.append(f"[{name}] 剩余筹码:{p.money}, 已下注:{p.money_indesk}")

        # 3. 将玩家状态拼接到全局状态下方
        state_strs.append("👤 【玩家状态】: " + " | ".join(player_strs))

        # 用换行符连接，让大模型阅读时更有层次感
        return "\n".join(state_strs)

    from typing import Optional

    def check_win(self) -> Optional[str]:
        alive_roles = [p.name for p in self.players.values() if p.is_have_money and p.name != "system"]
        if len(alive_roles) == 1:
            winner_name = alive_roles[0]
            return f"{winner_name}"

        # 如果还有多人生存，游戏继续
        return None

    def is_betting_balanced(self) -> bool:
        """判断当前存活玩家的下注额是否已经全部平齐"""

        active_players = [
            p for name, p in self.players.items()
            if p.is_in_game and name != "system"
        ]

        if len(active_players) <= 1:
            return True
        max_bet = max([p.money_indesk_cur for p in active_players] + [0])
        for p in active_players:
            if p.money_indesk_cur < max_bet:
                if p.money > 0:
                    return False

        # 如果所有人要么补齐了最高注，要么已经把命填进去了(All-in, money==0)
        return True
