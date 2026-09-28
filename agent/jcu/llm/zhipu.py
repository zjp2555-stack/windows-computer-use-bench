"""智谱 GLM 宿主 LLM 客户端（OpenAI 兼容的 chat/completions）。"""

from ..http_util import post_json

URL = "https://open.bigmodel.cn/api/paas/v4/chat/completions"


class ZhipuChat:
    def __init__(self, api_key: str, model: str = "glm-4.6"):
        self.api_key = api_key
        self.model = model

    def chat(self, system: str, user: str, temperature: float = 0.2) -> str:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
        }
        data = post_json(
            URL, {"Authorization": f"Bearer {self.api_key}"}, payload
        )
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as exc:
            raise RuntimeError(f"GLM 返回结构异常: {data}") from exc
