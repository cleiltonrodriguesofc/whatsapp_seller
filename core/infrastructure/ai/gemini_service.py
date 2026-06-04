"""
Gemini AI service implementation.

Drop-in replacement for OpenAIService using Google's Gemini API.
Implements the same AIService interface with identical method signatures.
"""

import os
import logging
from typing import Optional
from google import genai
from core.application.interfaces import AIService

logger = logging.getLogger(__name__)


class GeminiService(AIService):
    """
    Implementation of AIService using Google's Gemini API.
    """

    def __init__(self):
        self.api_key = os.environ.get("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY not found in environment")
        self.client = genai.Client(api_key=self.api_key)
        self.model = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")

    async def chat(self, message: str, context: Optional[str] = None) -> str:
        """Sends a chat message to Gemini and returns the response."""
        full_prompt = message
        if context:
            full_prompt = f"{context}\n\n{message}"

        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=full_prompt,
            )
            return response.text or ""
        except Exception as exc:
            logger.error("gemini api call failed: %s", exc, exc_info=True)
            raise

    async def generate_affiliate_copy(
        self, title: str, price: float, old_price: Optional[float], discount: float, link: str,
        installment_text: str = "", pix_discount_text: str = ""
    ) -> str:
        """Generates persuasive WhatsApp copy for an affiliate product offer."""
        old_str = f"R$ {old_price:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") if old_price else "Não informado"
        price_str = f"R$ {price:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

        prompt = f"""
Você é um especialista em vendas no WhatsApp. Crie uma copy curta, persuasiva e muito atrativa para este produto:

Produto: {title}
Preço Atual: {price_str}
Preço Antigo: {old_str}
Desconto: {discount:.0f}%
Parcelamento: {installment_text}
Desconto no Pix: {pix_discount_text}
Link: {link}

⚠️ REGRA CRÍTICA: Não foque apenas em dados técnicos (como GHz ou GB). Fale sobre FINALIDADES e BENEFÍCIOS REAIS.
- Se for notebook: é bom para estudar? jogar? editar vídeos/design? trabalhar sem travar?
- Se for celular: a câmera é incrível para o Instagram/TikTok? a bateria não te deixa na mão? roda jogos pesados?
- Se for TV/Eletrodoméstico: qual o conforto ou praticidade que traz para o lar?

Formato OBRIGATÓRIO:
1. Um GANCHO chamativo focando na principal utilidade (ex: "Procurando um notebook que não trava nos estudos e no trabalho?").
2. O preço incrível (ex: "🔥 De ~{old_str}~ por apenas *{price_str}*!").
3. Adicione informações de parcelamento ou pix se estiverem disponíveis de forma sucinta.
4. 2 a 3 tópicos curtos (com emojis) dizendo o que ele FAZ DE MELHOR na prática.
5. Chamada para ação final simples, terminando EXATAMENTE com o link: 👉 {link}

Seja objetivo, pule linhas para facilitar a leitura no WhatsApp e não use hashtags.
"""
        return await self.chat(message=prompt)
