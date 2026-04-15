# -*- coding: utf-8 -*-
"""大模型输出的结构化约束契约"""
from pydantic import BaseModel, Field
from typing import Optional, List, Literal

class ActionModel(BaseModel):
    """出牌阶段的行动模型"""
    action_type: Literal["add_stakes", "follow_stakes","check","all_in","fold"] = Field(
        description="选择 'add_stakes' 加注，或选择 'follow_stakes' 跟注,或选择 'check' 过牌,或选择 'all in' 全下,或者选择 'fold' 弃牌"
    )
    add_stakes: Optional[str] = Field(
        description="当你选择加注（add_stakes）时，填写你要加注的筹码数量（必须大于当前最高下注）。请确保你有足够的筹码来加注，并且这是一个合理的决策。否则填 null",
        default=None
    )
    follow_stakes: Optional[str] = Field(
        description="当你选择跟注（follow）时，表示你同意投入与当前最高下注相同数量的筹码以继续参与游戏。请确保你有足够的筹码来跟注，并且这是一个合理的决策。否则填 null",
        default=None
    )
    check: Optional[bool] = Field(
        description="当你已经下的注码等于目前的最大下注时，你可以选择过牌（check），表示不加注但保留继续参与的权利。否则填 false",
        default=None
    )
    all_in: Optional[bool] = Field(
        description="当你选择全下（all in）时，表示你将剩余的所有筹码投入底池。请确保你确实想要全下，因为这是一种极端的策略。否则填 false",
        default=None
    )
    fold: Optional[bool] = Field(
        description="当你选择弃牌（fold）时，表示你放弃本轮的竞争，不再参与当前底池的争夺。请确保你确实想要弃牌，因为这意味着你将失去本轮投入的筹码，并且无法赢得当前底池。否则填 false",
        default=False
    )
    reasoning: str = Field(description="内部思维链：简述你基于当前身份、局势做出该决策的理由")

class SimpleTraitModel(BaseModel):
    """极简的玩家打牌风格模型"""
    style_name: str = Field(description="风格标签（如：'莽夫'、'苟王'、'记仇'、'算计'）")
    action_rule: str = Field(description="一句非常具体、接地气的打牌习惯描述（绝对不要反智）。可以类似：'喜欢all in,赌对面不敢跟' 或 '当别人一旦加重注就容易弃牌,除非牌非常大'")