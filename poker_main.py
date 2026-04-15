# -*- coding: utf-8 -*-
"""三国杀主事件引擎与入口"""
import asyncio
import os
import random
from agentscope.agent import ReActAgent
from agentscope.model import OpenAIChatModel
from agentscope.message import Msg
from agentscope.formatter import DashScopeMultiAgentFormatter
import agentscope
agentscope.init(logging_level="ERROR")

from poker_state import PlayerState
from typing import List
from poker_schemas import ActionModel,  SimpleTraitModel
from poker_state import GameEngine
from poker_prompts import get_poker_system_prompt, get_simple_trait_prompt
from treys import Card, Evaluator
from poker_config import generate_poker_deck
# 5名首发武将
NAMES = ["丹牛", "布兰妮", "毒王", "谭轩", "Yara"]
ROLES_SETUP = ["小盲", "普通玩家", "普通玩家", "普通玩家", "普通玩家"]
CARD_NUMES = ['0','3','1','1']
sb_amount = 20
bb_amount = 40
import sys
class CleanOutputFilter:
    """
    终极输出拦截器：物理掐断所有包含特定底层关键字的打印请求
    """

    def __init__(self, original_stdout):
        self.original_stdout = original_stdout

    def write(self, text):
        # 🚨 黑名单关键字：只要这句打印内容里包含这些词，直接丢弃！
        blacklist = [
            '"type": "tool_use"',
            '"type": "tool_result"',
            '"name": "generate_response"',
            "Successfully generated response."
        ]

        # 检查文本是否命中黑名单
        if any(keyword in text for keyword in blacklist):
            return  # 物理丢弃，什么都不做

        # 如果是干净的文本（比如你的 broadcast），正常放行
        self.original_stdout.write(text)

    def flush(self):
        self.original_stdout.flush()
sys.stdout = CleanOutputFilter(sys.stdout)
class pokerGame:
    def __init__(self):
        # 随机分配身份

        self.engine = GameEngine(NAMES, ROLES_SETUP)
        self.agents = {}
        self.belief_states = {name: "游戏刚开始，尚未收集到任何情报。" for name in NAMES}
        
        # 初始化模型 (如果配置了环境变量，这里的占位符会被覆盖)
        self.model = OpenAIChatModel(
            model_name=os.getenv("LLM_MODEL_ID", "qwen-plus-2025-12-01"),
            api_key=os.getenv("LLM_API_KEY", "YOUR_API_KEY_HERE"),
            client_kwargs={
                "base_url": os.getenv("LLM_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
            }

        )
        
    async def broadcast(self, content: str):
        """全局播报"""
        print(f"📢 [系统播报]: {content}")
        msg = Msg(name="System", role="system", content=content)
        for agent in self.agents.values():
            await agent.observe(msg)
    def convert_to_treys_card(card_str: str) -> int:
        """
        将带符号的卡牌字符串 (如 '♠A', '♥10') 转换为 treys 的内部整数表示
        """
        # 提取花色和点数 (支持 '10' 占用两个字符的情况)
        suit_symbol = card_str[0]
        rank_symbol = card_str[1:]

        # 映射字典
        suit_map = {'♠': 's', '♥': 'h', '♦': 'd', '♣': 'c'}

        # 将 '10' 转换为 treys 认识的 'T'
        if rank_symbol == '10':
            rank_symbol = 'T'

        treys_str = rank_symbol + suit_map.get(suit_symbol, 's')
        return Card.new(treys_str)

    async def win_condition_check(self):
        evaluator = Evaluator()
        # 1. 获取公共牌
        board_cards = [Card.new(c['treys_val']) for c in self.engine.players["system"].hand_cards]

        # 2. 收集所有未弃牌玩家的牌力分数和本局总投入 (使用你原有的 money_indesk)
        survivors = []
        for name, p in self.engine.players.items():
            if name == "system" or not p.is_in_game:
                continue

            hand_cards = [Card.new(c['treys_val']) for c in p.hand_cards]
            score = evaluator.evaluate(board_cards, hand_cards)
            survivors.append({
                "name": name,
                "score": score,
                "invest": p.money_indesk  # 🚨 使用你原本就有的累计投入变量
            })

        msg = [f"\n🏆 ======= 本局结算 (Showdown) ======="]
        total_pot = self.engine.players["system"].money
        msg.append(f"💰 总底池: {total_pot}")

        # 3. 剥洋葱式结算算法 (逐级处理主池和边池)
        # 只要还有幸存者在比牌，并且总池里还有钱，就继续分
        while survivors and total_pot > 0:
            # 找到当前存活者中投入最少的人（通常是全下的短码）
            min_invest = min(s['invest'] for s in survivors)

            # 计算当前这层池子的大小
            # 规则：所有人（包括已弃牌的）最多只能为这一层贡献 min_invest
            current_layer_pot = 0
            for name, p in self.engine.players.items():
                if name == "system":
                    continue
                # 从每个人的总投入里，切下最多 min_invest 这么大的一块钱放进当前池
                contribution = min(p.money_indesk, min_invest)
                current_layer_pot += contribution
                p.money_indesk -= contribution  # 切完就扣掉

            # 从系统总池里把分出去的这部分钱减掉
            total_pot -= current_layer_pot

            # 找出当前这层池子的赢家（分数【越低】越好！）
            best_score = min(s['score'] for s in survivors)
            layer_winners = [s['name'] for s in survivors if s['score'] == best_score]

            # 获取牌型名称
            hand_class = evaluator.get_rank_class(best_score)
            hand_name = evaluator.class_to_string(hand_class)

            # 平分这层的池子
            split_amount = current_layer_pot // len(layer_winners)
            msg.append(f"📦 结算池层级 (额度:{current_layer_pot}) | 获胜牌型: {hand_name}")

            for winner in layer_winners:
                self.engine.players[winner].money += split_amount
                msg.append(f"  🎉 {winner} 赢得: {split_amount - self.engine.players[winner].money_indesk }")

            # 处理无法平分的奇数零头
            remainder = current_layer_pot % len(layer_winners)
            if remainder > 0:
                self.engine.players[layer_winners[0]].money += remainder
                msg.append(f"  ⚖️ 零头 {remainder} 归于 {layer_winners[0]}")

            # 核心逻辑：剥洋葱！
            # 1. 把投入已经在这轮扣完的玩家踢出下一轮比拼（比如全下100块的曹操，他没资格赢更厚的边池）
            survivors = [s for s in survivors if s['invest'] > min_invest]

            # 2. 剩下的人，把他们参与比拼的筹码额度同步扣掉刚才分走的那一层
            for s in survivors:
                s['invest'] -= min_invest

        # 4. 扫尾清空
        self.engine.players["system"].money = 0
        # 注意：因为前面切洋葱的时候，p.money_indesk 已经被扣到 0 了，
        # 但为了安全起见，依然建议在这里显式重置一下，防止有死代码残留
        for name, p in self.engine.players.items():
            if name != "system":
                p.money_indesk = 0
                p.money_indesk_cur = 0  # 顺手把当前轮的注也清空，保持干净

        # 5. 破产淘汰检查
        msg.append("-----------------------------------------")
        for name, p in self.engine.players.items():
            if name == "system":
                continue
            # 兜底：哪怕有人因为边池赢了一点点钱，只要不够1块钱也算破产
            if p.money <= 0:
                p.money = 0  # 防止负数
                p.is_have_money = False
                p.is_in_game = False
                msg.append(f"💀 {name} 筹码耗尽，破产淘汰！")

        # 6. 全场播报
        await self.broadcast("\n".join(msg))
    async def play_phase(self, active_name: str):
        """出牌阶段循环"""
        active_agent = self.agents[active_name]
        active_state = self.engine.players[active_name]

        
        while active_state.is_have_money and active_state.is_in_game:
            public_info = self.engine.get_public_state()
            hand_info = active_state.get_hand_str()
            print(f"{active_name} 拥有的手牌: {hand_info}")
            current_belief = self.belief_states[active_name]
            
            poker_public = self.engine.players["system"].get_hand_str()
            add_money = active_state.money

            if(self.engine.players[active_name].money_indesk_cur == self.engine.players["system"].money_indesk_cur):
                poker_public += f", 目前无人下注,你可以选择让牌"
            else:
                poker_public += f", 目前有人下注,你必须加注或者跟注或者弃牌"
            if add_money>0:
                poker_public += f", 你目前的筹码足够你最大加注{add_money}筹码"
            elif add_money == 0:
                poker_public += f", 你目前的筹码只能跟注，无法加注"
            else:
                poker_public += f", 你目前的筹码不足以跟注，也无法加注"
            msg = Msg(
                name="System", role="system",
                content=(
                    f"=== 你的出牌阶段 ===\n场上公开信息为 {public_info}\n"
                    f"【潜意识唤醒】：请严格遵循你的玩家设定 -> {active_state.personality_profile}\n"
                    f"【你的内部推理记忆】: {current_belief}\n"
                    f"你的剩余筹码: {active_state.money}\n，你已经下注的筹码{active_state.money_indesk},目前已经开出的公共牌{poker_public}你的手牌: {hand_info}\n"
                    f"你需要选择是加注还是跟注或者弃牌\n"
                )
            )
            
            # [架构师优化]: 加入网络容错重试机制 (最高重试 3 次)
            data = None
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    res = await active_agent(msg, structured_model=ActionModel)
                    data = res.metadata
                    break # 成功则跳出重试循环
                except Exception as e:
                    # print(f"   [网络异常] {active_name} 报错: {type(e).__name__} - {str(e)}")
                    if attempt < max_retries - 1:
                        print(f"   [网络波动] {active_name} 的大模型请求超时，正在进行第 {attempt+1} 次重试...")
                        await asyncio.sleep(2) # 缓冲2秒
                    else:
                        await self.broadcast(f"模型请求连续失败，请检查网络连接与模型服务状态。")
                        exit(1) # 连续失败则退出程序
            





            if not data:
                break
            if data.get("action_type") == "check":
                # 过牌不需要投入任何筹码，只需向全场播报即可
                if active_state.money_indesk_cur<self.engine.players['system'].money_indesk_cur and active_state.money>=self.engine.players['system'].money_indesk_cur-active_state.money_indesk_cur:
                    await self.broadcast(f"{active_name} 过牌，但当前已有玩家下注，你需要至少跟注才能继续参与本轮。所以系统修正为跟注")
                    money_put = self.engine.players["system"].money_indesk_cur - active_state.money_indesk_cur
                    active_state.money -= money_put
                    active_state.money_indesk += money_put
                    active_state.money_indesk_cur = self.engine.players["system"].money_indesk_cur
                    self.engine.players["system"].money += money_put
                    await self.broadcast(f"{active_name} 跟注")

                elif active_state.money_indesk_cur<self.engine.players['system'].money_indesk_cur and active_state.money<self.engine.players['system'].money_indesk_indesk_cur-active_state.money_indesk_cur:
                    await self.broadcast(f"{active_name} 过牌，但当前已有玩家下注，并且筹码不足以跟注。所以系统修正为弃牌")
                    active_state.is_in_game = False
                    await self.broadcast(f"{active_name} 弃牌。")
                else:
                    await self.broadcast(f"{active_name} 过牌。")
            elif data.get("action_type") == "all_in":
                # 全下：把玩家手里所有剩余的钱全推进底池
                all_in_money = active_state.money

                # 1. 扣除玩家手里的筹码并累加到本轮面前
                active_state.money = 0
                active_state.money_indesk += all_in_money
                active_state.money_indesk_cur += all_in_money
                active_state.all_in = True

                # 2. 将全下的钱加入主底池
                self.engine.players["system"].money += all_in_money
                self.engine.players["system"].money_indesk_cur = max(
                    self.engine.players["system"].money_indesk_cur,
                    active_state.money_indesk_cur
                )
                await self.broadcast(f"{active_name} 全下 (All-in)！推入了 {all_in_money} 筹码。")
            elif data.get("action_type") == "add_stakes":

                add_money = active_state.money - int(data.get("add_stakes", 0))
                if(add_money<0):
                    await self.broadcast(f"{active_name} 选择加注{data.get('add_stakes', 0)}筹码,但筹码不足以支持他加注,系统修改为全下。")
                    all_in_money = active_state.money

                    # 1. 扣除玩家手里的筹码并累加到本轮面前
                    active_state.money = 0
                    active_state.money_indesk += all_in_money
                    active_state.money_indesk_cur += all_in_money
                    active_state.all_in = True

                    # 2. 将全下的钱加入主底池
                    self.engine.players["system"].money += all_in_money
                    self.engine.players["system"].money_indesk_cur = max(
                        self.engine.players["system"].money_indesk_cur,
                        active_state.money_indesk_cur
                    )
                    await self.broadcast(f"{active_name} 全下 (All-in)！推入了 {all_in_money} 筹码。")
                else:
                    active_state.money -= int(data.get("add_stakes", 0))
                    active_state.money_indesk += int(data.get("add_stakes", 0))
                    active_state.money_indesk_cur += int(data.get("add_stakes", 0))

                    self.engine.players["system"].money+= int(data.get("add_stakes", 0))
                    self.engine.players["system"].money_indesk_cur = max(self.engine.players["system"].money_indesk, active_state.money_indesk_cur)
                    await self.broadcast(f"{active_name} 加注到{active_state.money_indesk_cur}。")
            elif data.get("action_type") == "follow_stakes":
                all_money = active_state.money
                money_put = self.engine.players["system"].money_indesk_cur - active_state.money_indesk_cur
                active_state.money -=money_put
                if active_state.money < 0:
                    await self.broadcast(f"{active_name} 选择跟注,但筹码不足以支持他跟注,系统修改为全下。")

                    # 1. 扣除玩家手里的筹码并累加到本轮面前
                    active_state.money = 0
                    active_state.money_indesk += all_money
                    active_state.money_indesk_cur += all_money
                    active_state.all_in = True

                    # 2. 将全下的钱加入主底池
                    self.engine.players["system"].money += all_money
                    self.engine.players["system"].money_indesk_cur = max(
                        self.engine.players["system"].money_indesk_cur,
                        active_state.money_indesk_cur
                    )
                    await self.broadcast(f"{active_name} 全下 (All-in)！推入了 {all_money} 筹码。")
                else:
                    active_state.money_indesk += money_put
                    active_state.money_indesk_cur = self.engine.players["system"].money_indesk_cur

                    self.engine.players["system"].money+= money_put
                    await self.broadcast(f"{active_name} 跟注")
            else :
                await self.broadcast(f"{active_name} 弃牌。")
                active_state.is_in_game = False
            return
    def setup_new_round(self, names: List[str]) -> List[str]:
        """
        初始化新的一局：确定座位
        返回：排好序的玩家名字列表 (index 0 永远是小盲)
        """

        names = [name for name in names if self.engine.players[name].money > 0]
        sb_name = random.choice(names)
        sb_idx = names.index(sb_name)

        ordered_names = names[sb_idx:] + names[:sb_idx]
        return ordered_names
    def change_round(self, names: List[str]) -> List[str]:
        """
        初始化新的一局：移动盲注位，并剔除破产玩家
        传入的 names 是上一局的玩家顺序 (index 0 是上一局的小盲)
        返回：新一局排好序的玩家名字列表 (index 0 是新的小盲)
        """
        # 1. 数组左移 1 位，完成庄家/盲注的顺时针轮转
        shifted_names = names[1:] + names[:1]

        active_names = []
        for name in shifted_names:
            player = self.engine.players[name]
            # 双重保险：既要标记存活，也要账上有钱
            if player.is_have_money:
                active_names.append(name)

        self.engine.player_names = active_names

        return active_names
    def print_chip_status(self, game_time: int, phase_name: str):

        # 🚨 终极对齐小工具：专门解决中英文混合导致的排版错乱
        def align_text(text: str, target_width: int) -> str:
            # 遍历字符，如果是中文/全角符号(ASCII值>127)算作2个宽度，英文算1个宽度
            visual_length = sum(2 if ord(c) > 127 else 1 for c in str(text))
            # 算出还差多少个空格补齐
            padding = max(0, target_width - visual_length)
            return str(text) + " " * padding

        msg = []
        msg.append(f"\n📊 ======= 当前是第{game_time}局,{phase_name}阶段 =======")

        # ====== 新增：1. 核心公共牌信息 ======
        community_cards = self.engine.players["system"].get_hand_str()
        if not community_cards.strip():
            community_cards = "[未发牌]"
        msg.append(f"🎴 【当前公共牌】: {community_cards}")

        # 2. 核心底池信息
        main_pot = self.engine.players["system"].money
        msg.append(f"💰 【当前主底池】: {main_pot}")

        # 分割线稍微拉长一点
        msg.append("-" * 75)

        # 3. 玩家状态明细
        for name, p in self.engine.players.items():
            if name == "system":
                continue

            # 获取玩家底牌
            cards_str = p.get_hand_str()
            if not cards_str.strip():
                cards_str = "[无]"

            # 🚨 使用我们写的视觉对齐工具，设定名字专栏的固定宽度为 8
            name_aligned = align_text(name, 8)

            if not p.is_have_money:
                msg.append(f"💀 {name_aligned} | 状态: 破产淘汰")
            elif not p.is_in_game:
                # 即使弃牌了，上帝视角依然能看到他盖掉的是什么牌
                msg.append(
                    f"🏳️ {name_aligned} | 状态: 已弃牌 | 剩余: {p.money:<4} | 沉没成本: {p.money_indesk:<3} | 盖牌: {cards_str}")
            else:
                # 正常存活玩家的详细信息 (注意：数字因为都是英文宽，所以保留原有的 :<4 即可)
                msg.append(
                    f"👤 {name_aligned} | 剩余: {p.money:<4} | 总投入: {p.money_indesk:<3} | 本轮面前: {p.money_indesk_cur:<3} | 手牌: {cards_str}")

        # 打印到终端
        print("\n".join(msg))
    async def post_blinds(self, names: List[str]) -> bool:
        """
        处理强制盲注扣除，并在玩家破产时进行清理。
        返回 True 表示游戏可以继续，返回 False 表示存活人数不足，游戏需提前结束。
        """
        sb_name = names[0]
        bb_name = names[1]


        await self.broadcast("💵 正在收取盲注...")

        # --- 扣除小盲 (SB) ---
        sb_player = self.engine.players[sb_name]
        if sb_player.is_in_game and sb_player.is_have_money:
            if sb_player.money >= sb_amount:
                sb_player.money -= sb_amount
                sb_player.money_indesk = sb_amount
                sb_player.money_indesk_cur = sb_amount
                self.engine.players["system"].money += sb_amount
                await self.broadcast(f"  👉 {sb_name} 投入小盲注 {sb_amount}。剩余: {sb_player.money}")
            else:
                sb_player.is_in_game = False
                sb_player.is_have_money = False
                sb_player.money_indesk = 0
                await self.broadcast(f"  💀 {sb_name} 连小盲注 ({sb_amount}) 都交不起，惨遭破产淘汰！")

        # --- 扣除大盲 (BB) ---
        bb_player = self.engine.players[bb_name]
        if bb_player.is_in_game and bb_player.is_have_money:
            if bb_player.money >= bb_amount:
                bb_player.money -= bb_amount
                bb_player.money_indesk = bb_amount
                bb_player.money_indesk_cur = bb_amount
                self.engine.players["system"].money += bb_amount
                await self.broadcast(f"  👉 {bb_name} 投入大盲注 {bb_amount}。剩余: {bb_player.money}")
            else:
                bb_player.is_in_game = False
                bb_player.is_have_money = False
                bb_player.money_indesk = 0
                await self.broadcast(f"  💀 {bb_name} 连大盲注 ({bb_amount}) 都交不起，惨遭破产淘汰！")

        # --- 确立本局初始下注标尺 ---
        initial_highest = max([p.money_indesk for p in self.engine.players.values() if p.name != "system"], default=0)
        self.engine.players["system"].money_indesk_cur = initial_highest

        # --- 检查存活人数 ---
        active_players = [p for p in self.engine.players.values() if p.is_in_game]
        if len(active_players) <= 1:
            winner = self.engine.check_win()
            await self.broadcast(f"🏆 其他人交不起盲注破产，游戏提前结束！{winner} 获胜！")
            return False  # 告诉主程序不要往下走了

        return True  # 告诉主程序，可以发牌了
    async def run(self):
        """游戏主循环"""
        await self.broadcast("🎉 德扑 Agent 5人局 MVP 版本启动！")
        await self.broadcast("🧬 正在通过大模型为各位玩家注入真实的【灰度人格】灵魂，请稍候...")


        for i, name in enumerate(NAMES):
            print(f"\n⏳ 正在为玩家 [{name}] 随机抽取人类灵魂... ", end="", flush=True)
            
            # 生成一个 1~99999 的混沌种子，强迫大模型在隐空间中漫游
            chaos_seed = random.randint(1, 99999)
            
            # 临时Agent
            temp_agent = ReActAgent(
                name=f"Gen_HumanPlayer_{i}",
                sys_prompt="你是德扑玩家风格设定器。请严格按照要求执行工具调用，不要输出任何多余文本。",
                model=self.model,
                formatter=DashScopeMultiAgentFormatter(),
            )

            # 2. 依然贴上封口胶（堵住 DialogAgent 仅有的一次输出）
            temp_agent.speak = lambda msg: None
            # 传入混沌种子
            prompt_msg = Msg(name="System", role="system", content=get_simple_trait_prompt(chaos_seed))
            meta = None
            for attempt in range(3):
                try:
                    res = await temp_agent(prompt_msg, structured_model=SimpleTraitModel)
                    if res.metadata: 
                        meta = res.metadata
                        break
                except Exception:
                    await asyncio.sleep(1)
                    
            if meta:
                style_name = meta.get('style_name', '普通')
                action_rule = meta.get('action_rule', '正常打牌')
                profile = f"风格：{style_name}。习惯：{action_rule}"
                print(f"💡 [风格注入] {name} -> 【{style_name}】: {action_rule}")
            else:
                profile = "正常发挥，追求胜利。"
                print(f"⚠️ [风格注入] {name} -> 采用默认风格")

            self.engine.players[name].personality_profile = profile
            
            # 实例化正式Agent
            self.agents[name] = ReActAgent(
                name=name,
                sys_prompt=get_poker_system_prompt(name,  profile),
                model=self.model,
                formatter=DashScopeMultiAgentFormatter(),

            )
        # 确定座次 (只需要在游戏最开始调一次)
        names = self.setup_new_round(NAMES)
        game_round = 1

        while True:  # 外层循环：第几局
            winner = self.engine.check_win()
            if winner:
                await self.broadcast(f"🏆 {winner} 赢得了比赛的最终胜利！")
                return
            await self.broadcast(f"=== 德州扑克第 {game_round} 局开始 ===")


            # 1. 赛前重置与排座次 (庄家轮转)
            names = self.change_round(names)
            self.engine.players['system'].money_indesk_cur = 0
            self.engine.players['system'].money = 0
            self.engine.players['system'].hand_cards = []
            self.engine.deck = generate_poker_deck()
            for name in names:
                self.engine.reset_game(name)
                # 🃏 发底牌
                self.engine.draw_cards(name, 2)

            # 2. 定义德扑的四个固定阶段
            phases = [
                ("翻牌前", 0),
                ("翻牌圈", 3),
                ("转牌圈", 1),
                ("河牌圈", 1)
            ]
            game_over_early = False
            # 3. 按照阶段发牌与下注
            for phase_name, deal_count in phases:
                self.engine.players["system"].money_indesk_cur = 0
                for n in names:
                    self.engine.players[n].money_indesk_cur = 0
                # ====== A. 盲注与发牌逻辑 ======
                if deal_count == 0:
                    # 翻牌前：强制扣除盲注
                    post_blinds_result = await self.post_blinds(names)
                    if not post_blinds_result:
                        game_over_early = True
                        break
                else:
                    self.engine.draw_cards("system", deal_count)
                    plate = self.engine.players["system"].get_hand_str()
                    await self.broadcast(f"\n🎴【{phase_name}】发牌！当前公牌: {plate}")

                if phase_name == "翻牌前":
                    # 翻牌前：大盲左手边(枪口位 Index 2)先说话
                    start_index = 2
                else:
                    # 翻牌后：小盲(Index 0)先说话，且本轮下注额度清零
                    start_index = 0
                    self.engine.players["system"].money_indesk_cur = 0
                    for n in names:
                        self.engine.players[n].money_indesk_cur = 0

                # 清空本轮的表态名册
                players_acted = set()
                num_players = len(names)

                # ====== C. 核心下注状态机 (Spin-Lock) ======
                while True:
                    # 获取活着的、且有钱的玩家
                    active_names = [n for n in names if
                                    self.engine.players[n].is_in_game and self.engine.players[n].money > 0]
                    # 🚨 退出条件：所有活人都表态了，且筹码已经平衡
                    all_acted = all(n in players_acted for n in active_names)
                    if all_acted and self.engine.is_betting_balanced():
                        await self.broadcast(f"⚖️ 【{phase_name}】所有人均已表态且筹码平衡，本轮下注结束！")
                        for name in active_names:
                            player = self.engine.players[name]
                            player.money_indesk_cur = 0
                        self.engine.players['system'].money_indesk_cur = 0
                        break

                    # 开始按顺时针轮询
                    for i in range(num_players):
                        # 环形数组算法：确保从 start_index 开始，转一圈
                        current_idx = (start_index + i) % num_players
                        name = names[current_idx]
                        player = self.engine.players[name]

                        # 弃牌或破产的人直接跳过，并记入已表态名册
                        if not player.is_in_game or player.money == 0:
                            players_acted.add(name)
                            continue
                        # 如果他已经表态过，且他的钱不欠底池了，不要烦他
                        if name in players_acted and player.money_indesk_cur == self.engine.players["system"].money_indesk_cur or player.all_in:
                            continue
                        # ====== 真正的大模型决策时刻 ======
                        await self.broadcast(
                            f"【{phase_name}】阶段: 轮到 {name} 发言 )")
                        # 调用你的 Agent 思考函数 (你需要确保 play_phase 里有扣钱的物理操作)
                        await self.play_phase(name)
                        players_acted.add(name)

                        self.print_chip_status(game_round,phase_name)
                        winner = self.engine.check_win()
                        if winner:
                            await self.broadcast(f"🏆 其他人全部弃牌，{winner} 拿下了底池！")
                            game_over_early = True
                            break

                    if game_over_early:
                        break  # 跳出 while 循环

                if game_over_early:
                    break  # 跳出 phases 循环

            # 4. 摊牌比大小 (Showdown)
            if not game_over_early:
                await self.broadcast("\n💥 所有人跟注到底，进入摊牌阶段！")

                await self.win_condition_check()

            game_round += 1


if __name__ == "__main__":
    asyncio.run(pokerGame().run())