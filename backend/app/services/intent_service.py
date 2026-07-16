import re
from typing import Dict, Any

from ..interfaces.services import IIntentService

class IntentService(IIntentService):
    def __init__(self):
        self.rules = {
            "spreadsheet_generation": [
                r"\bexcel\b", r"\bspreadsheet\b", r"\bcsv\b", r"\bxlsx\b", r"\bsheet\b", 
                r"\bexpense tracker\b", r"\btable\b", r"\bdata sheet\b", r"\brow\b", r"\bcolumn\b"
            ],
            "data_visualization": [
                r"\bchart\b", r"\bplot\b", r"\bgraph\b", r"\bvisualize\b", r"\bdiagram\b", 
                r"\bbar chart\b", r"\bline chart\b", r"\bpie chart\b", r"\bhistogram\b", r"\bscatterplot\b"
            ],
            "code_generation": [
                r"\bcode\b", r"\bpython\b", r"\bscript\b", r"\bfunction\b", r"\bclass\b", 
                r"\bprogram\b", r"\balgorithm\b", r"\bwrite code\b", r"\bdevelop\b", r"\bcompile\b",
                r"\bc language\b", r"\bc\+\+\b", r"\bjava\b", r"\bjavascript\b", r"\bprogramming\b",
                r"\bhtml\b", r"\bcss\b"
            ],
            "translation": [
                r"\btranslate\b", r"\btranslation\b", r"\bforeign language\b", r"\btranslate to\b",
                r"\blanguage translation\b", r"\benglish\b", r"\bspanish\b", r"\bfrench\b",
                r"\bgerman\b", r"\bjapanese\b", r"\bchinese\b"
            ],
            "writing": [
                r"\bsummarize\b", r"\bsummary\b", r"\bemail\b", r"\bdraft\b", r"\bwrite\b", 
                r"\bessay\b", r"\bparagraph\b", r"\bletter\b", r"\bblog\b", r"\barticle\b"
            ]
        }

    def classify(self, prompt: str) -> Dict[str, Any]:
        normalized = prompt.strip().lower()
        scores = {intent: 0 for intent in self.rules}
        
        # Calculate scores based on regex matches
        for intent, patterns in self.rules.items():
            for pattern in patterns:
                if re.search(pattern, normalized):
                    scores[intent] += 1
        
        # Determine the best match
        best_intent = "general_reasoning"
        max_score = 0
        total_score = sum(scores.values())
        
        for intent, score in scores.items():
            if score > max_score:
                max_score = score
                best_intent = intent
        
        # Calculate confidence
        confidence = 0.5
        if total_score > 0:
            confidence = min(0.95, 0.5 + (max_score / total_score) * 0.45)
        elif "general_reasoning" == best_intent:
            confidence = 0.90
            
        return {
            "intent": best_intent,
            "confidence": round(confidence, 2),
            "normalized_prompt": prompt.strip()
        }
