import asyncio
import json
import os
from typing import Any, Literal, AsyncGenerator
from langgraph.graph import StateGraph, END

from core.logger import get_logger
from core.mysql_history import UserMySQLHistoryManager
from workflow.state import WorkflowState
from agents.chat import Chat
from agents.intent_recognizer import IntentRecognizer
from agents.route_plan import RoutePlannerAgent
from agents.reviewer import SubtitleReviewer
from agents.rewriter import SubtitleEditor
from agents.rag_generation import RAGPipeline

logger = get_logger(__name__)

class SubtitleGenerationWorkflow:
    def __init__(self, mcp_adapter):
        """初始化工作流，复用已建立的 MCP 长连接"""
        logger.info("初始化内容生成工作流（完整异步 + MCP 集成）")
        self.mcp_adapter = mcp_adapter

        # Agent 延迟初始化
        self.mcp_tools = None
        self.intent_recognizer = None
        self.route_plan = None
        self.chat = None
        self.reviewer = None
        self.rewriter = None
        self.rag = None

        self._stream_queue = asyncio.Queue()

    def _build_graph(self) -> Any:
        """构建工作流图"""
        workflow = StateGraph(state_schema=WorkflowState)

        # --- 添加节点 ---
        workflow.add_node("intent_recognition", self._intent_recognition_node)
        workflow.add_node("chat", self._chat_node)
        workflow.add_node("route_plan", self._route_plan_node)
        workflow.add_node("extract_audio", self._extract_audio_node)
        workflow.add_node("speech_to_text", self._speech_to_text_node)
        workflow.add_node("review", self._review_node)
        workflow.add_node("rewrite", self._rewrite_node)
        workflow.add_node("burn_subtitles", self._burn_subtitles_node)
        workflow.add_node("rag", self._rag_node)
        workflow.add_node("add_history", self._add_history_node)

        # --- 设置入口点 ---
        workflow.set_entry_point("intent_recognition")

        # --- 添加条件边 ---
        workflow.add_conditional_edges(
            "intent_recognition",
            self._route_by_intent,
            {
                "chat": "chat",
                "workflow": "extract_audio",
                "route_plan": "route_plan",
                "RAG": "rag",
            }
        )

        # --- 添加边 ---
        workflow.add_edge("chat", "add_history")
        workflow.add_edge("route_plan", "add_history")
        workflow.add_edge("rag", "add_history")
        workflow.add_edge("extract_audio", "speech_to_text")
        workflow.add_edge("speech_to_text", "review")

        # 审核后的条件边
        workflow.add_conditional_edges(
            "review",
            self._route_after_review,
            {
                "pass": "burn_subtitles",
                "rewrite": "rewrite",
                "fail": "add_history",
            }
        )
        workflow.add_edge("rewrite", "review")
        workflow.add_edge("burn_subtitles", "add_history")
        workflow.add_edge("add_history", END)

        return workflow.compile()

    async def _intent_recognition_node(self, state: WorkflowState) -> WorkflowState:
        """意图识别节点(异步)"""
        logger.info("执行节点: 意图识别")
        self._stream_queue.put_nowait(json.dumps({"t": "status", "c": "正在判断用户意图..."}, ensure_ascii=False))

        response = await self.intent_recognizer.recognize(state['user_input'])

        if response.success:
            result = response.content
            state['intent'] = result['intent']
            state['intent_confidence'] = result['confidence']
            logger.info(f"识别结果: {result['intent']} (置信度: {result['confidence']})")
        else:
            state['intent'] = 'chat'
            state['intent_confidence'] = 0.5
            logger.warning("意图识别失败,默认为普通对话")

        state["execution_path"].append("intent_recognition")
        return state

    async def _chat_node(self, state: WorkflowState) -> WorkflowState:
        """普通对话(含网络搜索)响应节点(异步)"""
        logger.info("执行节点: 智能对话")
        self._stream_queue.put_nowait(json.dumps({"t": "status", "c": "AI 思考中..."}, ensure_ascii=False))

        user_input = state.get("user_input", "")
        session_id = state.get("session_id", "")

        if not user_input:
            state["error"] = "无有效输入内容"
            return state

        try:
            full_response = ""
            async for chunk in self.chat.chat(user_input, session_id):
                if chunk:
                    full_response += chunk
                    self._stream_queue.put_nowait(json.dumps({"t": "token", "c": chunk}, ensure_ascii=False))

            state["final_output"] = full_response
            state["execution_path"].append("chat")
            logger.info("\n对话完成")
            return state

        except Exception as e:
            logger.error(f"Chat 节点运行异常: {str(e)}")
            state["error"] = str(e)
            return state

    async def _route_plan_node(self, state: WorkflowState) -> WorkflowState:
        """出行规划响应节点(多工具循环流式)"""
        logger.info("执行节点: 出行规划")
        self._stream_queue.put_nowait(json.dumps({"t": "status", "c": "正在规划任务..."}, ensure_ascii=False))

        user_query = state.get("user_input", "")

        if not user_query:
            state["error"] = "未提供出行规划的具体需求"
            return state

        try:
            full_plan = ""
            async for text_chunk in self.route_plan.stream_plan(user_query, session_id=state.get("session_id")):
                if text_chunk:
                    full_plan += text_chunk
                    self._stream_queue.put_nowait(json.dumps({"t": "token", "c": text_chunk}, ensure_ascii=False))

            state["final_output"] = full_plan
            state["execution_path"].append("route_plan")
            logger.info("\n规划方案生成完毕")
            return state

        except Exception as e:
            logger.error(f"RoutePlan 节点运行异常: {str(e)}")
            state["error"] = str(e)
            return state

    async def _extract_audio_node(self, state: WorkflowState) -> WorkflowState:
        """提取音频节点"""
        logger.info("执行节点: 提取音频")
        self._stream_queue.put_nowait(json.dumps({"t": "status", "c": "正在提取音频..."}, ensure_ascii=False))

        video_path = state.get('original_video_path', '')

        if not video_path:
            state['error'] = '缺失 video_path，无法提取音频'
            return state

        try:
            # 从 MCP 获取提取音频的工具函数
            extract_tool = self.mcp_adapter._create_tool_function("ffmpeg_extract_audio")

            result = await extract_tool(video_path=video_path)

            if "Error" in result or not result:
                state['error'] = result
                return state

            logger.info("音频提取完成")
            state['audio_path'] = result
            state["execution_path"].append("extract_audio")

            return state

        except Exception as e:
            logger.error(f"提取音频节点异常: {str(e)}")
            state['error'] = str(e)
            return state

    async def _speech_to_text_node(self, state: WorkflowState) -> WorkflowState:
        """语音转字幕节点"""
        logger.info("执行节点: 语音转字幕")
        self._stream_queue.put_nowait(json.dumps({"t": "status", "c": "正在生成字幕..."}, ensure_ascii=False))

        audio_path = state.get('audio_path', '')

        if not audio_path:
            state['error'] = '缺失 audio_path，无法进行语音转录'
            return state

        try:
            whisper_tool = self.mcp_adapter._create_tool_function('whisper_speech_to_text')

            result = await whisper_tool(
                audio_path=audio_path,
                # initial_prompt=state.get('user_input', '')
            )

            if 'Error' in result or not result:
                state['error'] = result
                return state
            else:
                srt_path = result

            srt_content = await self.mcp_adapter.read_resource(f"mcp://file/subtitle/{srt_path}")

            if not srt_content:
                state['error'] = f"已生成字幕文件 {srt_path} 但读取内容为空"
                return state

            logger.info("语音转录完成")
            state['original_srt_path'] = srt_path
            state["execution_path"].append("speech_to_text")

            return state

        except Exception as e:
            logger.error(f"语音转录节点异常: {str(e)}")
            state['error'] = str(e)
            return state

    async def _review_node(self, state: WorkflowState) -> WorkflowState:
        """字幕审核节点"""
        loop = state.get('loop_count', 0)
        logger.info(f"执行节点: 字幕审核 (第 {loop + 1} 轮)")
        status_msg = f"正在审核字幕质量...（第 {loop + 1} 轮）" if loop > 0 else "正在审核字幕质量..."
        self._stream_queue.put_nowait(json.dumps({"t": "status", "c": status_msg}, ensure_ascii=False))

        srt_path = state.get('original_srt_path')
        audio_path = state.get('audio_path')

        if not srt_path or not audio_path:
            state['error'] = "审核失败：缺失字幕文件名或音频路径"
            return state

        try:
            loop_count = state.get('loop_count', 0)
            # 动态判断 Prompt和Resource：初审用 review_subtitle_prompt，复审用 second_review_prompt
            prompt_name = "review_subtitle_prompt" if loop_count == 0 else "second_review_prompt"
            srt_path = srt_path if loop_count == 0 else state.get('final_srt_path')

            # 如果是复审，传入上一轮的反馈 review_feedback
            response = await self.reviewer.review(
                srt_path=srt_path,
                audio_path=audio_path,
                prompt_name=prompt_name,
                review_feedback=state.get('review_feedback', "")
            )

            if not response.success:
                state['error'] = f"审核 Agent 执行失败: {response.error}"
                return state

            state['review_feedback'] = response.content
            state['execution_path'].append('review')

            if "【校验通过】" in response.content:
                state['review_passed'] = True
                logger.info("✓ 字幕审核通过")
            else:
                state['review_passed'] = False
                logger.info("✗ 字幕审核未通过，准备修正")

            return state

        except Exception as e:
            logger.error(f"审核节点异常: {str(e)}")
            state['error'] = str(e)
            return state

    async def _rewrite_node(self, state: WorkflowState) -> WorkflowState:
        """字幕修正节点"""
        logger.info("执行节点: 字幕修正")
        loop = state.get('loop_count', 0)
        self._stream_queue.put_nowait(json.dumps({"t": "status", "c": f"正在根据建议修正字幕...（第 {loop + 1} 轮）"}, ensure_ascii=False))

        srt_path = state.get('original_srt_path')
        feedback = state.get('review_feedback')

        if not feedback:
            state['error'] = "修正失败：未获取到审核反馈意见"
            return state

        try:
            response = await self.rewriter.rewrite(
                srt_path=srt_path,
                review_feedback=feedback,
            )

            if not response.success:
                state['error'] = f"修正 Agent 执行失败: {response.error}"
                return state

            final_path = response.metadata.get('final_path')

            state['final_srt_path'] = final_path
            state['loop_count'] = state.get('loop_count', 0) + 1  # 循环计数增加
            state['execution_path'].append('rewrite')

            logger.info(f"字幕修正完成，新版本已保存至: {final_path}")

            return state

        except Exception as e:
            logger.error(f"修正节点异常: {str(e)}")
            state['error'] = str(e)
            return state

    async def _burn_subtitles_node(self, state: WorkflowState) -> WorkflowState:
        """字幕烧录节点：将字幕压制进视频"""
        logger.info("执行节点: 字幕烧录")
        self._stream_queue.put_nowait(json.dumps({"t": "status", "c": "正在压制视频字幕..."}, ensure_ascii=False))

        video_path = state.get('original_video_path')
        srt_path = state.get('final_srt_path') or state.get('original_srt_path')

        if not video_path or not srt_path:
            state['error'] = "烧录失败：缺失视频路径或字幕路径"
            return state

        try:
            burn_tool = self.mcp_adapter._create_tool_function('ffmpeg_burn_subtitles')
            result = await burn_tool(
                video_path=video_path,
                srt_path=srt_path,
            )

            if "Error" in result or not result:
                state['error'] = result
                return state

            base_url = "http://localhost:8000"
            base_name = os.path.basename(result)
            video_url = f"{base_url}/static_videos/{base_name}"

            state['final_video_path'] = video_url
            loop_count = state.get('loop_count', 0)
            report = "✨ **视频字幕处理已完成！**\n\n"
            if loop_count > 0:
                report += f"经过 {loop_count} 轮精密校对，我已经根据审核建议修正了转录中的偏差，并完成了视频压制。\n"
            else:
                report += "转录内容经校验质量极高，已直接为您完成字幕烧录。\n"
            report += "\n🎬 最终视频已就绪，请在下方查看或下载。"

            state['final_output'] = report
            state['execution_path'].append('burn_subtitles')

            logger.info(f"✓ 视频烧录完成: {result}")

            return state
        except Exception as e:
            logger.error(f"字幕烧录节点异常: {str(e)}")
            state['error'] = str(e)
            return state

    async def _rag_node(self, state: WorkflowState) -> WorkflowState:
        """RAG 检索增强生成节点"""
        logger.info("执行节点: RAG 知识库检索")
        self._stream_queue.put_nowait(json.dumps({"t": "status", "c": "正在检索知识库..."}, ensure_ascii=False))

        user_input = state.get("user_input", "")
        if not user_input:
            state["error"] = "RAG 节点未接收到有效用户输入"
            return state

        full_response = ""
        try:
            async for chunk in self.rag.generate_answer(query=user_input, session_id=state.get("session_id")):
                if chunk:
                    full_response += chunk
                    self._stream_queue.put_nowait(json.dumps({"t": "token", "c": chunk}, ensure_ascii=False))

            state["final_output"] = full_response
            state["execution_path"].append("rag")

            logger.info("✓ RAG 回答生成完毕")
            return state
        except Exception as e:
            logger.error(f"RAG 节点执行异常: {str(e)}")
            state["error"] = f"RAG 检索失败: {str(e)}"
            return state

    async def _add_history_node(self, state: WorkflowState) -> WorkflowState:
        """历史记录归档节点：将本次执行结果存入 MySQL，并推送完成事件"""
        logger.info("执行节点: 历史记录归档")
        self._stream_queue.put_nowait(json.dumps({"t": "status", "c": "正在保存历史会话..."}, ensure_ascii=False))

        uid = state.get("uid")
        session_id = state.get("session_id")
        user_input = state.get("user_input", "")
        original_video = state.get("original_video_path")

        final_output = state.get("final_output", "")
        final_video = state.get("final_video_path")

        def _emit_events():
            if state.get("error"):
                self._stream_queue.put_nowait(json.dumps({"t": "error", "c": state["error"]}, ensure_ascii=False))
            self._stream_queue.put_nowait(json.dumps({
                "t": "done",
                "video_url": state.get("final_video_path", ""),
                "content": state.get("final_output", ""),
                "session_id": state.get("session_id", ""),
                "intent": state.get("intent", ""),
            }, ensure_ascii=False))

        if not uid:
            logger.warning("未发现 UID，跳过历史记录保存")
            _emit_events()
            return state

        try:
            user_turn = [{"type": "text", "content": user_input}]
            if original_video:
                user_turn.append({"type": "file", "file_path": original_video})

            assistant_turn = [{"type": "text", "content": final_output}]
            if final_video:
                assistant_turn.append({"type": "file", "file_path": final_video})

            new_history_entry = {
                "user": user_turn,
                "assistant": assistant_turn,
            }

            history_manager = UserMySQLHistoryManager(uid=uid)

            actual_session_id = history_manager.save(
                session_id=session_id,
                qa=[new_history_entry]
            )

            state["session_id"] = actual_session_id
            state["execution_path"].append("add_history")

            logger.info(f"✓ 历史记录已保存至 session: {actual_session_id}")

        except Exception as e:
            logger.error(f"保存历史记录失败: {str(e)}")

        _emit_events()
        return state

    def _route_by_intent(self, state: WorkflowState) -> Literal["chat", "workflow", "route_plan", "RAG"]:
        """根据意图识别结果选择主分支"""
        intent = state.get("intent", "chat")

        logger.info(f"意图路由中: {intent}")
        return intent

    def _route_after_review(self, state: WorkflowState) -> Literal["pass", "rewrite", "fail"]:
        """判断审核是否通过，或是否需要继续修正"""
        # 如果发生节点错误，进入错误处理逻辑
        if state.get("error"):
            logger.error(f"工作流因错误中断: {state['error']}")
            return "fail"

        # 检查审核结果
        if state.get("review_passed"):
            logger.info("审核状态: 已通过，准备烧录视频")
            return "pass"

        # 最多允许修正 3 次
        max_loops = 3
        if state.get("loop_count", 0) >= max_loops:
            logger.warning(f"已达到最大修正次数 ({max_loops})，强制终止修正循环并执行烧录")
            return "pass"

        # 审核未通过且未达次数上限，继续修正
        logger.info(f"审核状态: 未通过，进入第 {state.get('loop_count', 0) + 1} 次修正")
        return "rewrite"

    async def _ensure_ready(self):
        """确保共享资源已加载（mcp_tools、graph 等，全生命周期仅初始化一次）"""
        if not hasattr(self, 'mcp_tools') or self.mcp_tools is None:
            self.mcp_tools = await self.mcp_adapter.get_langgraph_tools()
            logger.info("MCP 工具已加载并缓存")

    async def _prepare_agents(self, uid: str):
        """根据传入的 uid 初始化 Agent（共享资源缓存，用户相关按需重建）"""
        await self._ensure_ready()

        # ── 共享 Agent + Graph（不依赖 uid，只初始化一次）──
        if self.intent_recognizer is None:
            self.intent_recognizer = IntentRecognizer()
            self.reviewer = SubtitleReviewer(self.mcp_tools, self.mcp_adapter)
            self.rewriter = SubtitleEditor(self.mcp_tools, self.mcp_adapter)
            self.graph = self._build_graph()
            logger.info("共享 Agent 与 LangGraph 图已构建并缓存")

        # ── 用户相关 Agent（依赖 uid，每次切换用户/首次请求时重建）──
        current_uid = getattr(self, '_current_uid', None)
        if self.chat is None or current_uid != uid:
            self._current_uid = uid
            self.chat = Chat(self.mcp_tools, self.mcp_adapter, uid)
            self.route_plan = RoutePlannerAgent(uid=uid)
            self.rag = RAGPipeline(collection_name=uid, uid=uid)
            logger.info(f"用户 {uid} 专属 Agent 已初始化（记忆/向量集绑定）")

    async def run_stream(self, initial_params: dict) -> AsyncGenerator[str, None]:
        uid = initial_params.get("uid")
        if not uid:
            raise ValueError("运行工作流必须提供 uid")
        await self._prepare_agents(uid)
        state: WorkflowState = {
            "uid": initial_params.get("uid"),
            "session_id": initial_params.get("session_id"),
            "user_input": initial_params.get("user_input", ""),
            "original_video_path": initial_params.get("original_video_path", ""),
            "audio_path": "",
            "original_srt_path": "",
            "final_srt_path": "",
            "final_video_path": "",
            "intent": "chat",
            "intent_confidence": 0.0,
            "review_feedback": "",
            "review_passed": False,
            "final_output": "",
            "loop_count": 0,
            "execution_path": [],
            "error": None
        }

        def sse(event_type: str, **payload) -> str:
            payload["type"] = event_type
            return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


        async def _run_graph():
            try:
                await self.graph.ainvoke(state)
            finally:
                self._stream_queue.put_nowait(None)

        graph_task = asyncio.create_task(_run_graph())

        try:
            while True:
                item = await self._stream_queue.get()
                if item is None:
                    break
                payload = json.loads(item)
                t = payload.get("t")
                if t == "token":
                    yield sse("answer", content=payload["c"])
                elif t == "status":
                    yield sse("status", content=payload["c"])
                elif t == "done":
                    yield sse("done",
                        video_url=payload.get("video_url", ""),
                        content=payload.get("content", ""),
                        session_id=payload.get("session_id", ""),
                        intent=payload.get("intent", ""),
                    )
                elif t == "error":
                    yield sse("error", content=payload["c"])

            await graph_task
            yield "data: [DONE]\n\n"

        except Exception as e:
            logger.error(f"Stream Error: {str(e)}", exc_info=True)
            yield sse("error", content=str(e))
            if not graph_task.done():
                graph_task.cancel()




