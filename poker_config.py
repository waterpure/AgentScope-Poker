import uuid
import random
from typing import List, Dict


def generate_poker_deck() -> List[Dict]:
    """
    生成标准 52 张德州扑克牌库
    采用笛卡尔积保证牌的绝对唯一性，并双向适配大模型与底层计算引擎
    """
    deck = []

    # UI显示与大模型认知用 -> 底层 treys 计算用 的映射
    # treys 要求的花色格式: s(spades), h(hearts), d(diamonds), c(clubs)
    suit_map = {
        "♠": "s",
        "♥": "h",
        "♦": "d",
        "♣": "c"
    }

    # 点数：10 用 T 表示，这是扑克算法的国际通用标准
    RANKS = ['2', '3', '4', '5', '6', '7', '8', '9', 'T', 'J', 'Q', 'K', 'A']

    for suit_icon, suit_letter in suit_map.items():
        for rank in RANKS:
            # 构建传给 treys 的标准字符串 (例如: 'As', 'Th', '2d')
            treys_val = f"{rank}{suit_letter}"

            deck.append({
                "uuid": str(uuid.uuid4())[:8],
                "suit": suit_icon,
                "rank": rank,
                "name": f"{suit_icon}{rank}",  # 侧重表现层：给 AI 和控制台看的 (如 "♠A")
                "treys_val": treys_val  # 侧重物理层：传给 Evaluator 计算用的 (如 "As")
            })

    # 洗牌 (In-place 打乱)
    random.shuffle(deck)

    return deck