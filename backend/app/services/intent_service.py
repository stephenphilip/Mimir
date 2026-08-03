import re
from typing import Dict, Any

from ..interfaces.services import IIntentService


class IntentService(IIntentService):
    def __init__(self):
        self.rules = {
            "document_generation": [
                r"\bpdf\b",
                r"\bdocument\b",
                r"\breport\b",
                r"\bworkout\b",
                r"\bplan\b",
                r"\bfpdf\b",
                r"\breportlab\b",
                r"\bgenerate a pdf\b",
                r"\bcreate a pdf\b",
                r"\bmake a pdf\b",
            ],
            "spreadsheet_generation": [
                r"\bexcel\b",
                r"\bspreadsheet\b",
                r"\bcsv\b",
                r"\bxlsx\b",
                r"\bsheet\b",
                r"\bexpense tracker\b",
                r"\btable\b",
                r"\bdata sheet\b",
                r"\brow\b",
                r"\bcolumn\b",
            ],
            "data_visualization": [
                r"\bchart\b",
                r"\bplot\b",
                r"\bgraph\b",
                r"\bvisualize\b",
                r"\bdiagram\b",
                r"\bbar chart\b",
                r"\bline chart\b",
                r"\bpie chart\b",
                r"\bhistogram\b",
                r"\bscatterplot\b",
            ],
            "code_generation": [
                r"\bcode\b",
                r"\bpython\b",
                r"\bscript\b",
                r"\bfunction\b",
                r"\bclass\b",
                r"\bprogram\b",
                r"\balgorithm\b",
                r"\bwrite code\b",
                r"\bdevelop\b",
                r"\bcompile\b",
                r"\bc language\b",
                r"\bc\+\+\b",
                r"\bjava\b",
                r"\bjavascript\b",
                r"\bprogramming\b",
                r"\bhtml\b",
                r"\bcss\b",
            ],
            "translation": [
                r"\btranslate\b",
                r"\btranslation\b",
                r"\bforeign language\b",
                r"\btranslate to\b",
                r"\blanguage translation\b",
            ],
            "writing": [
                r"\bsummarize\b",
                r"\bsummary\b",
                r"\bemail\b",
                r"\bdraft\b",
                r"\bessay\b",
                r"\bparagraph\b",
                r"\bletter\b",
                r"\bblog\b",
                r"\barticle\b",
            ],
            "image_generation": [
                r"\bgenerate (an? )?image\b",
                r"\bcreate (an? )?image\b",
                r"\bdraw (an?|me)\b",
                r"\billustration\b",
                r"\bcomfyui\b",
                r"\bdall-?e\b",
                r"\btext to image\b",
                r"\btext-to-image\b",
            ],
            "vision_analysis": [
                r"\bocr\b",
                r"\bread (this|the) (image|screenshot|photo|scan)\b",
                r"\bdescribe (this|the) (image|screenshot|photo)\b",
                r"\bwhat.?s in (this|the) (image|picture|photo)\b",
                r"\bscanned document\b",
            ],
        }

    def classify(self, prompt: str) -> Dict[str, Any]:
        normalized = prompt.strip().lower()
        scores = {intent: 0 for intent in self.rules}

        for intent, patterns in self.rules.items():
            for pattern in patterns:
                if re.search(pattern, normalized):
                    scores[intent] += 1

        # Boost PDF/doc phrasing even if only one keyword hits
        if re.search(r"\b(pdf|document|report)\b", normalized) and (
            re.search(r"\b(generate|create|make|build|write)\b", normalized)
        ):
            scores["document_generation"] += 2

        best_intent = "general_reasoning"
        max_score = 0
        total_score = sum(scores.values())

        for intent, score in scores.items():
            if score > max_score:
                max_score = score
                best_intent = intent

        confidence = 0.5
        if total_score > 0:
            confidence = min(0.95, 0.5 + (max_score / total_score) * 0.45)
        elif best_intent == "general_reasoning":
            confidence = 0.90

        return {
            "intent": best_intent,
            "confidence": round(confidence, 2),
            "normalized_prompt": prompt.strip(),
        }
