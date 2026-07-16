from typing import List, Dict, Any

from ..interfaces.services import ICapabilityService

class CapabilityService(ICapabilityService):
    def __init__(self):
        # Maps intents to required system capabilities
        self.capability_map = {
            "spreadsheet_generation": ["reasoning", "python_execution", "excel_generation"],
            "data_visualization": ["reasoning", "python_execution", "chart_generation"],
            "code_generation": ["reasoning", "coding"],
            "translation": ["reasoning", "translation"],
            "writing": ["reasoning", "text_processing"],
            "general_reasoning": ["reasoning"]
        }

    def resolve(self, intent: str) -> List[str]:
        # Return capabilities required for a given intent
        return self.capability_map.get(intent, ["reasoning"])

    def get_execution_requirements(self, capabilities: List[str]) -> Dict[str, Any]:
        # Determine execution runtime and package requirements
        requirements = {
            "runtime": "python" if "python_execution" in capabilities else None,
            "packages": []
        }
        
        if "excel_generation" in capabilities:
            requirements["packages"].extend(["pandas", "openpyxl"])
        if "chart_generation" in capabilities:
            requirements["packages"].extend(["matplotlib", "seaborn", "pandas"])
            
        # Deduplicate packages
        requirements["packages"] = list(set(requirements["packages"]))
        return requirements
