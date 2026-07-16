import json
import time
from typing import Generator

from .context import ExecutionContext
from ..interfaces.services import (
    IIntentService,
    ICapabilityService,
    IContextBuilder,
    IModelSelector,
    IExecutionEngine,
    IPlanner,
    IModelService
)
from ..interfaces.providers import IProvider
from ..interfaces.repositories import IConversationRepository, IModelRepository

class Orchestrator:
    def __init__(
        self,
        intent_service: IIntentService,
        capability_service: ICapabilityService,
        context_builder: IContextBuilder,
        model_selector: IModelSelector,
        provider: IProvider,
        execution_engine: IExecutionEngine,
        planner: IPlanner,
        model_service: IModelService,
        conversation_repo: IConversationRepository,
        model_repo: IModelRepository
    ):
        self.intent_service = intent_service
        self.capability_service = capability_service
        self.context_builder = context_builder
        self.model_selector = model_selector
        self.provider = provider
        self.execution_engine = execution_engine
        self.planner = planner
        self.model_service = model_service
        self.conversation_repo = conversation_repo
        self.model_repo = model_repo

    def process_prompt(self, conversation_id: str, prompt: str) -> Generator[str, None, None]:
        """Stream orchestration steps as JSON event strings."""
        try:
            # 1. Initialize ExecutionContext
            context = ExecutionContext(prompt=prompt)
            context.execution_status = "running"
            
            # Load conversation
            conv = self.conversation_repo.get_by_id(conversation_id)
            if conv:
                context.conversation = {"id": conv.id, "title": conv.title, "user_id": conv.user_id}
            else:
                context.conversation = {"id": conversation_id, "title": "New Chat", "user_id": 1}

            # 2. Save user message
            user_message = self.conversation_repo.add_message(
                conv_id=conversation_id,
                sender="user",
                content=prompt
            )
            context.user = {"id": user_message.conversation.user_id if user_message.conversation else 1}

            # 3. Intent Engine
            yield f"data: {json.dumps({'type': 'status', 'status': 'Detecting intent...'})}\n\n"
            intent_res = self.intent_service.classify(prompt)
            context.intent = intent_res["intent"]
            context.intent_confidence = intent_res["confidence"]
            yield f"data: {json.dumps({'type': 'status', 'status': f'Detected intent: {context.intent} (confidence {context.intent_confidence})'})}\n\n"

            # 4. Capability Engine
            yield f"data: {json.dumps({'type': 'status', 'status': 'Mapping capabilities...'})}\n\n"
            context.capabilities = self.capability_service.resolve(context.intent)
            yield f"data: {json.dumps({'type': 'status', 'status': f'Requirements: {', '.join(context.capabilities)}'})}\n\n"

            # 5. Planner
            self.planner.create_plan(context)

            # 6. Context Builder
            self.context_builder.build_context(context)

            # 7. Model Selection & Download Verification
            yield f"data: {json.dumps({'type': 'status', 'status': 'Determining target model...'})}\n\n"
            self.model_service.sync_models_to_db()
            
            # Fetch available models & hardware information
            installed_models = self.model_repo.get_all_installed()
            available_model_names = [m.name for m in installed_models if m.status == "installed"]
            hw = self.model_service.detect_hardware()
            
            target_model = self.model_selector.select_best_model(context, available_model_names, context.capabilities, hw)
            context.selected_model = target_model
            context.selected_provider = "ollama"
            yield f"data: {json.dumps({'type': 'status', 'status': f'Target model: {target_model}'})}\n\n"

            installed = self.model_repo.get_by_name(target_model)
            active_model = target_model
            bypassed = False
            
            if installed and installed.status == "installed":
                yield f"data: {json.dumps({'type': 'status', 'status': f'Selected active model: {active_model}'})}\n\n"
            else:
                # Target not installed. Look for fallback
                ready_installed = [m for m in installed_models if m.status == "installed"]
                if ready_installed:
                    fallback_model = ready_installed[0].name
                    tokens_per_sec = 40.0 if hw["has_gpu"] else 8.0
                    prompt_tokens = len(prompt) / 4.0
                    expected_response_tokens = 400.0
                    
                    t_exec_fallback = (prompt_tokens + expected_response_tokens) / tokens_per_sec
                    
                    def get_model_size_gb(model: str) -> float:
                        if "7b" in model or "8b" in model:
                            return 4.7
                        if "3b" in model:
                            return 2.0
                        if "1.5b" in model:
                            return 0.9
                        if "1b" in model:
                            return 1.3
                        return 2.0
                    
                    size_gb = get_model_size_gb(target_model)
                    download_speed_gbps = 0.005  # 5 MB/s
                    t_download_target = size_gb / download_speed_gbps
                    t_exec_target = t_exec_fallback
                    
                    t_total_target = t_download_target + t_exec_target
                    threshold = 0.5 * t_total_target
                    
                    if t_exec_fallback < threshold:
                        bypassed = True
                        active_model = fallback_model
                        yield f"data: {json.dumps({
                            'type': 'status', 
                            'status': f'Bypassing download of {target_model} (Est. download+run: {int(t_total_target)}s). '
                                      f'Running on loaded model {fallback_model} (Est. run: {int(t_exec_fallback)}s < 50% threshold {int(threshold)}s).'
                        })}\n\n"
                        # Download target model in background
                        self.model_service.trigger_background_download(target_model)
                    else:
                        yield f"data: {json.dumps({'type': 'status', 'status': f'Bypass threshold exceeded. Downloading target model {target_model}...'})}\n\n"
                        self.model_service.trigger_background_download(target_model)
                else:
                    yield f"data: {json.dumps({'type': 'status', 'status': f'No models loaded. Downloading target model {target_model}...'})}\n\n"
                    self.model_service.trigger_background_download(target_model)

            if not bypassed and active_model == target_model:
                while True:
                    # Expire repository session cache to pull fresh records
                    self.model_repo.refresh()
                    inst = self.model_repo.get_by_name(active_model)
                    if inst and inst.status == "installed":
                        break
                    
                    dl = self.model_repo.get_download(active_model)
                    if dl:
                        if dl.status == "downloading":
                            yield f"data: {json.dumps({'type': 'download_progress', 'model': active_model, 'progress': dl.progress})}\n\n"
                        elif dl.status == "failed":
                            yield f"data: {json.dumps({'type': 'error', 'message': f'Failed to download model {active_model}: {dl.error}'})}\n\n"
                            return
                        elif dl.status == "completed":
                            break
                    else:
                        self.model_service.trigger_background_download(active_model)
                    time.sleep(1.0)

            # 8. Unload other models
            yield f"data: {json.dumps({'type': 'status', 'status': 'Optimizing memory... Unloading other models.'})}\n\n"
            self.model_service.unload_other_models(active_model)

            # 9. Stream Inference
            yield f"data: {json.dumps({'type': 'status', 'status': f'Generating response using {active_model}...'})}\n\n"
            
            system_prompt = context.execution_metadata.get("system_prompt", "")
            user_prompt = context.execution_metadata.get("user_prompt", "")
            
            assistant_content = ""
            for chunk in self.provider.generate_stream(active_model, user_prompt, system_prompt):
                assistant_content += chunk
                yield f"data: {json.dumps({'type': 'content', 'text': chunk})}\n\n"

            context.execution_metadata["assistant_response"] = assistant_content

            # 10. Save assistant message
            assistant_message = self.conversation_repo.add_message(
                conv_id=conversation_id,
                sender="assistant",
                content=assistant_content
            )
            context.execution_metadata["assistant_message_id"] = assistant_message.id

            # 11. Tool Execution Pipeline
            if "python_execution" in context.capabilities:
                yield f"data: {json.dumps({'type': 'status', 'status': 'Executing generated python code...'})}\n\n"
                
                # Execute Python code via Engine
                exec_result = self.execution_engine.execute(context)
                
                # Yield results
                yield f"data: {json.dumps({
                    'type': 'execution_result',
                    'success': exec_result['success'],
                    'stdout': exec_result['stdout'],
                    'stderr': exec_result['stderr'],
                    'exit_code': exec_result['exit_code'],
                    'artifacts': exec_result['artifacts']
                })}\n\n"

            # Update conversation timestamp & title
            new_title = prompt[:30] + "..." if len(prompt) > 30 else prompt
            self.conversation_repo.update_title(conversation_id, new_title)

            yield f"data: {json.dumps({'type': 'done', 'conversation_id': conversation_id})}\n\n"
        except Exception as e:
            # Yield error event so the UI gets a proper notification and doesn't hang
            yield f"data: {json.dumps({'type': 'error', 'message': f'Internal Server Error: {str(e)}'})}\n\n"
