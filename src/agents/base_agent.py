import anthropic
import os
from dotenv import load_dotenv

load_dotenv()

class BaseAgent:
    def __init__(self, name: str, role: str):
        self.name = name
        self.role = role
        self.client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        self.model = "claude-sonnet-4-20250514"
    
    def call_llm(self, prompt: str, max_tokens: int = 1500) -> str:
        """Appelle Claude et retourne la réponse texte."""
        message = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        if not message.content:
            return ""
        return message.content[0].text
    
    def run(self, **kwargs):
        """Chaque agent implémente sa propre logique ici."""
        raise NotImplementedError("Chaque agent doit implémenter run()")
    
    def __repr__(self):
        return f"Agent({self.name} | {self.role})"