import json
from typing import Generator
from sqlalchemy.orm import Session
from ..db import Message, Conversation
from ..services.intent_service import IntentService
from ..services.capability_service import CapabilityService
from ..services.memory_service import MemoryService
from ..services.model_service import ModelService
from ..services.provider_service import OllamaProvider
from ..services.execution_service import ExecutionService

class Orchestrator:
    def __init__(self):
        self.intent_service = IntentService()
        self.capability_service = CapabilityService()
        self.memory_service = MemoryService()
        self.model_service = ModelService()
        self.provider = OllamaProvider()
        self.execution_service = ExecutionService()

    def process_prompt(self, db: Session, conversation_id: str, prompt: str) -> Generator[str, None, None]:
        """Stream orchestration steps as JSON event strings."""
        
        # 1. Save user message
        user_message = Message(
            conversation_id=conversation_id,
            sender="user",
            content=prompt
        )
        db.add(user_message)
        db.commit()
        db.refresh(user_message)

        # 2. Intent Engine
        yield f"data: {json.dumps({'type': 'status', 'status': 'Detecting intent...'})}\n\n"
        intent_res = self.intent_service.classify(prompt)
        intent = intent_res["intent"]
        confidence = intent_res["confidence"]
        yield f"data: {json.dumps({'type': 'status', 'status': f'Detected intent: {intent} (confidence {confidence})'})}\n\n"

        # 3. Capability Engine
        yield f"data: {json.dumps({'type': 'status', 'status': 'Mapping capabilities...'})}\n\n"
        capabilities = self.capability_service.resolve(intent)
        yield f"data: {json.dumps({'type': 'status', 'status': f'Requirements: {', '.join(capabilities)}'})}\n\n"

        # 4. Context Builder
        recent_context = self.memory_service.get_recent_context(db, conversation_id, limit=6)

        # 5. Model Manager Selection & Download Verification
        yield f"data: {json.dumps({'type': 'status', 'status': 'Determining target model...'})}\n\n"
        target_model = self.model_service.select_best_model(capabilities, db)
        yield f"data: {json.dumps({'type': 'status', 'status': f'Target model: {target_model}'})}\n\n"

        from ..db import InstalledModel, Download
        installed = db.query(InstalledModel).filter(InstalledModel.name == target_model).first()
        
        active_model = target_model
        bypassed = False
        
        if installed and installed.status == "installed":
            yield f"data: {json.dumps({'type': 'status', 'status': f'Selected active model: {active_model}'})}\n\n"
        else:
            # Target not installed. Look for fallback
            installed_models = db.query(InstalledModel).filter(InstalledModel.status == "installed").all()
            if installed_models:
                fallback_model = installed_models[0].name
                hw = self.model_service.detect_hardware()
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
            import time
            while True:
                db.expire_all()
                inst = db.query(InstalledModel).filter(InstalledModel.name == active_model).first()
                if inst and inst.status == "installed":
                    break
                
                dl = db.query(Download).filter(Download.model_name == active_model).first()
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

        # Unload all other models to ensure single model loaded in RAM
        yield f"data: {json.dumps({'type': 'status', 'status': 'Optimizing memory... Unloading other models.'})}\n\n"
        self.model_service.unload_other_models(active_model)

        # Build System Prompt with capabilities, profile, and instructions
        profile = self.memory_service.get_user_profile(db)
        settings = self.memory_service.get_settings(db)
        personality = settings.get("personality", "helpful, concise assistant")
        user_name = profile.get("name", "User")
        
        system_prompt = (
            f"You are a local AI personal assistant. Your name is Mimir.\n"
            f"User name: {user_name}.\n"
            f"Personality: {personality}.\n"
            f"Capabilities: You have access to {', '.join(capabilities)}.\n"
        )

        if "python_execution" in capabilities:
            system_prompt += (
                "IMPORTANT: To solve spreadsheet, csv, charts, or math tasks, you MUST write executable Python code inside a "
                "```python ... ``` code block. Use libraries like pandas, openpyxl, and matplotlib. "
                "All files generated MUST be saved directly to the current working directory. "
                "Provide brief, clean Python scripts that perform the entire task, then print a short success message. "
                "Do not explain the code too much; focus on writing correct python code that generates the files requested."
            )

        # Format prompt with context history
        full_context_prompt = ""
        for msg in recent_context:
            role_label = "User" if msg["role"] == "user" else "Assistant"
            full_context_prompt += f"{role_label}: {msg['content']}\n"
        full_context_prompt += f"User: {prompt}\nAssistant:"

        # 6. Stream Inference
        yield f"data: {json.dumps({'type': 'status', 'status': f'Generating response using {active_model}...'})}\n\n"
        
        assistant_content = ""
        for chunk in self.provider.generate_stream(active_model, full_context_prompt, system_prompt):
            assistant_content += chunk
            yield f"data: {json.dumps({'type': 'content', 'text': chunk})}\n\n"

        # 7. Save assistant message
        assistant_message = Message(
            conversation_id=conversation_id,
            sender="assistant",
            content=assistant_content
        )
        db.add(assistant_message)
        db.commit()
        db.refresh(assistant_message)

        # 8. Execution Pipeline (Tool Executor)
        if "python_execution" in capabilities:
            code = self.execution_service.extract_python_code(assistant_content)
            if code:
                yield f"data: {json.dumps({'type': 'status', 'status': 'Executing generated python code...'})}\n\n"
                
                # Execute Python
                exec_result = self.execution_service.execute_code(code, assistant_message.id, db)
                
                # Yield results
                yield f"data: {json.dumps({
                    'type': 'execution_result',
                    'success': exec_result['success'],
                    'stdout': exec_result['stdout'],
                    'stderr': exec_result['stderr'],
                    'exit_code': exec_result['exit_code'],
                    'artifacts': exec_result['artifacts']
                })}\n\n"
            else:
                yield f"data: {json.dumps({'type': 'status', 'status': 'No code block detected for execution.'})}\n\n"

        # Update conversation timestamp
        conv = db.query(Conversation).filter(Conversation.id == conversation_id).first()
        if conv:
            conv.title = prompt[:30] + "..." if len(prompt) > 30 else prompt
            db.commit()

        yield f"data: {json.dumps({'type': 'done', 'conversation_id': conversation_id})}\n\n"
