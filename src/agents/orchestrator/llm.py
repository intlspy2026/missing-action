from typing import Any, AsyncIterator, Dict, Iterator, List, Optional
from openai import RateLimitError
from langchain_core.callbacks import (
    AsyncCallbackManagerForLLMRun,
    CallbackManagerForLLMRun,
)
from requests.exceptions import HTTPError
import os
import sys
import yaml
import json
import httpx
from typing import Annotated, Any, Generator, Optional, Sequence, TypedDict, Union, Dict, List, AsyncIterator, Iterator, Literal
from uuid import uuid4
from langchain_core.language_models import LanguageModelLike
from langchain_core.messages import (
    AIMessage,
    AIMessageChunk,
    BaseMessage,
    convert_to_openai_messages,
    SystemMessage,
    HumanMessage
)
from langchain_core.runnables import RunnableConfig, RunnableLambda
from langchain_core.tools import BaseTool
from langchain_core.messages import HumanMessage, AIMessage
from langchain_openai import AzureChatOpenAI
from langchain_core.language_models.chat_models import ChatGeneration
from langchain_core.language_models import BaseChatModel
from langchain_core.outputs import ChatResult
import requests
from langchain_core.caches import BaseCache
from langchain_core.callbacks import Callbacks
from langchain_core.runnables.config import RunnableConfig
from langchain_core.utils.function_calling import convert_to_openai_tool
from langchain_core.prompt_values import PromptValue, ChatPromptValue

from pydantic import BaseModel, Field

from langchain_community.adapters.openai import (
    convert_dict_to_message,
    convert_message_to_dict,
)
import logging
logger = logging.getLogger(__name__)


class OpenAIProxyConfig(BaseModel):
    workspace_url: str
    workspace_id: str
    proxy_client_id: str
    proxy_client_secret: str
    proxy_cluster_id: str
    proxy_port: str
    proxy_route: str
    openai_api_key: str
    openai_api_version: str


ToolChoiceLiteral = Literal["auto", "none", "required"]
ToolChoiceInput = Optional[Union[ToolChoiceLiteral,
                                 str, "BaseTool", Dict[str, Any]]]


class ProxyChatModel(BaseChatModel):
    """A custom LangChain chat model for Smart Investigator
    - This chat model replicates Azure_ChatOpenAI in langchain_core in terms of input and output
    - It supports tool calling as well
    """

    proxy_config: OpenAIProxyConfig
    llm_config: List[Dict]
    deployment_name: str
    ratelimit_response: Optional[bool] = False

    # ---- Defaults you want to set at init ----
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    reasoning_effort: Optional[str] = None

    # Pass-through bag for any other OpenAI-compatible parameters
    # e.g., top_p, frequency_penalty, presence_penalty, response_format, seed, etc.
    model_kwargs: Dict[str, Any] = Field(default_factory=dict)

    @property
    def _llm_type(self) -> str:
        return "payg"

    def _create_chat_result(self, response: dict) -> ChatResult:
        """Convert LLM output payload into LangChain ChatResult object"""
        generations = []
        if not isinstance(response, dict):
            response = response.dict()

        for res in response["choices"]:
            message = convert_dict_to_message(res["message"])
            generation_info = dict(finish_reason=res.get("finish_reason"))
            if "logprobs" in res:
                generation_info["logprobs"] = res["logprobs"]

            gen = ChatGeneration(
                message=message,
                generation_info=generation_info,
            )
            generations.append(gen)

        token_usage = response.get("usage", {})
        llm_output = {
            "token_usage": token_usage,
            "model": response.get("model", ""),
            "llm_name": response.get("llm_name", ""),
            "system_fingerprint": response.get("system_fingerprint", ""),
        }
        return ChatResult(generations=generations, llm_output=llm_output)

    def _create_ratelimit_chat_result(self) -> ChatResult:
        """generate fall back response"""
        return ChatResult(generations=[ChatGeneration(text="I am sorry, I am unable to give you an answer right now but have found the following relevant articles below that may contain the answer. Please refer to these articles. If you want to try again to generate an answer, please try resubmitting your question.", generation_info={'finish_reason': 'stop', 'logprobs': None}, message=AIMessage(content="I am sorry, I am unable to give you an answer right now but have found the following relevant articles below that may contain the answer. Please refer to these articles. If you want to try again to generate an answer, please try resubmitting your question."))], llm_output={'token_usage': {'completion_tokens': 0, 'prompt_tokens': 0, 'total_tokens': 0}, 'model': 'NA', 'sk_llm_name': 'NA', 'system_fingerprint': 'NA'})

    def generate_sp_token(self):
        # Retrieve Service Principal OAuth token
        token_endpoint = f"{self.proxy_config.workspace_url}/oidc/v1/token"
        data = {
            "grant_type": "client_credentials",
            "scope": "all-apis"
        }
        headers = {
            "Content-Type": "application/x-www-form-urlencoded"
        }
        response = requests.post(url=token_endpoint, headers=headers, data=data, auth=(
            self.proxy_config.proxy_client_id, self.proxy_config.proxy_client_secret))
        response.raise_for_status()

        token = response.json()["access_token"]
        return token

    def get_openai_proxy_endpoint(self) -> (str, Dict, Dict):
        token = self.generate_sp_token()
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
            "api-key": f"{self.proxy_config.openai_api_key}"
        }
        params = {'api-version': self.proxy_config.openai_api_version}
        dp_endpoint = f"{self.proxy_config.workspace_url}/driver-proxy-api/o/{self.proxy_config.workspace_id}/{self.proxy_config.proxy_cluster_id}/{self.proxy_config.proxy_port}/{self.proxy_config.proxy_route}"
        return dp_endpoint, headers, params

    def _invoke_with_fallback(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any
    ) -> ChatResult:

        input_payload = {'messages': [
            convert_message_to_dict(m) for m in messages]}

        if stop:
            input_payload.update({"stop": stop})

        # ---- 1) defaults from init ----
        # (only set if not None; avoids sending unset keys)
        if self.temperature is not None:
            input_payload["temperature"] = self.temperature
        if self.max_tokens is not None:
            input_payload["max_tokens"] = self.max_tokens
        if self.reasoning_effort is not None:
            input_payload["reasoning_effort"] = self.reasoning_effort
        if self.model_kwargs:
            # top_p, response_format, frequency_penalty, etc.
            input_payload.update(self.model_kwargs)

        input_payload.update(**kwargs)

        # Inject tool schemas if bound
        if hasattr(self, "_bound_tools"):
            input_payload["tools"] = [convert_to_openai_tool(
                tool) for tool in self._bound_tools]

            # Add normalized tool_choice if present
            tc = getattr(self, "_tool_choice", None)
            if tc is not None:
                input_payload["tool_choice"] = tc

        endpoint = None
        # Loop through all LLMs defined in the configuration file, from top to bottom.
        # If hitting a Ratelimit error, then try the next fallback LLM option
        output = None
        exceptions = []

        try:
            # Get proxy endpoint, header, and params
            (endpoint, headers, params) = self.get_openai_proxy_endpoint()

            if self.reasoning_effort is None:
                # Chat Completions API (non-reasoning models)
                url = f"{endpoint}/openai/deployments/{self.deployment_name}/chat/completions"
            else:
                # Responses API (reasoning models)
                url = f"{endpoint}/openai/v1/chat/completions"

            input_payload["model"] = "gpt-5"  # Example placeholder from code
            if "max_tokens" in input_payload:
                input_payload["max_completion_tokens"] = input_payload.pop(
                    "max_tokens")

            params = {}
            # Move messages to 'input' for responses
            # input_payload["input"] = input_payload.pop("messages")
            print(input_payload)

            response = requests.post(url=url,
                                     headers=headers,
                                     params=params,
                                     json=input_payload)
            response.raise_for_status()
            llm_response = response.json()
            llm_response.update({'llm_name': 'payg'})
            output = self._create_chat_result(llm_response)

        except (HTTPError, RateLimitError) as rle:
            # Note that if it is hitting the proxy, the exception is HTTPError instead of RateLimitError
            if rle.response.status_code == 429:
                logger.warning(
                    f'RateLimitError occurs when hitting endpoint {endpoint}.\nTrying fallback options.')
                exceptions.append(rle)
            raise (rle)
        except Exception as e:
            raise (e)

        if not output:
            # If output is None then means all the possible fallback options gave RateLimitError
            # Check if we need to return curated ratelimit response or raise an exception
            if self.ratelimit_response:
                output = self._create_ratelimit_chat_result()
            else:
                raise exceptions[-1]

        return output

    def bind_tools(self, tools: List[BaseTool], tool_choice: ToolChoiceInput = None) -> "ProxyChatModel":
        """
        Return a shallow copy of this model with tools (and optional tool_choice) bound.

        tool_choice can be:
        - "auto" | "none" | "required"
        - "{tool_name}" (string)
        - BaseTool instance
        - Raw dict, e.g., {"type": "function", "function": {"name": "{tool_name}"}}
        """

        bound_model = ProxyChatModel(
            deployment_name=self.deployment_name,
            ratelimit_response=self.ratelimit_response,
            proxy_config=self.proxy_config,
            llm_config=self.llm_config,
            # Add other init args as needed
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            model_kwargs=self.model_kwargs
        )
        # Assuming further implementation of binding tools to the new instance
        return bound_model

    @staticmethod
    def _normalize_tool_choice(tool_choice: ToolChoiceInput, tools: List["BaseTool"]) -> Optional[Union[str, Dict[str, Any]]]:
        """
        Normalize tool_choice into the OpenAI 'tool_choice' payload format or return None.

        Returns:
            - None (if not provided)
            - One of "auto", "none", "required"
            - {"type": "function", "function": {"name": "<tool_name>"}}
        """
        if tool_choice is None:
            return None

        # Allowed literals pass-through
        if isinstance(tool_choice, str) and tool_choice in {"auto", "none", "required"}:
            return tool_choice

        tool_names = {t.name for t in tools}

        # If it's a BaseTool instance
        try:
            from langchain_core.tools import BaseTool  # adjust import to your env
            if isinstance(tool_choice, BaseTool):
                name = tool_choice.name
                if name not in tool_names:
                    raise ValueError(
                        f"tool_choice refers to tool '{name}' not in bound tools: {tool_names}")
                return {"type": "function", "function": {"name": name}}
        except Exception:
            # If BaseTool import or isinstance check fails, we silently ignore and continue checks below.
            pass

        # If it's a string => either a tool literal (handled above) or a tool name
        if isinstance(tool_choice, str):
            name = tool_choice
            if name not in tool_names:
                raise ValueError(
                    f"tool_choice refers to tool '{name}' not in bound tools: {tool_names}")
            return {"type": "function", "function": {"name": name}}

        # If it's a raw dict, accept but lightly validate (optional)
        if isinstance(tool_choice, dict):
            # Typical structure: {"type": "function", "function": {"name": "<tool_name>"}}
            type_ = tool_choice.get("type")
            func = tool_choice.get("function", {})
            name = func.get("name")
            if type_ == "function" and isinstance(name, str):
                if name not in tool_names:
                    raise ValueError(
                        f"tool_choice refers to tool '{name}' not in bound tools: {tool_names}")
                return tool_choice

            # Otherwise, pass-through to allow advanced usage; comment out the next line to be strict.
            return tool_choice

        raise TypeError(
            "tool_choice must be one of: None, 'auto'|'none'|'required', tool name (str), "
            "BaseTool instance, or a dict matching OpenAI tool_choice format."
        )


def _generate(
    self,
    messages: List[BaseMessage],
    stop: Optional[List[str]] = None,
    run_manager: Optional[CallbackManagerForLLMRun] = None,
    **kwargs: Any,
) -> ChatResult:
    return self._invoke_with_fallback(messages=messages, stop=stop, run_manager=run_manager, **kwargs)


def _coerce_to_lc_messages(
    self,
    input: Union[
        List[BaseMessage],
        List[Dict[str, str]],
        BaseMessage,
        Dict[str, str],
        str,
    ],
) -> List[BaseMessage]:
    """Coerce various LCEL inputs into a list of LangChain BaseMessage."""
    # 1) ChatPromptValue (what `ChatPromptTemplate` produces)
    if isinstance(input, ChatPromptValue):
        return input.to_messages()

    # 2) Any PromptValue (e.g., StringPromptValue)
    if isinstance(input, PromptValue):
        try:
            return input.to_messages()
        except Exception:
            # Fallback: treat as a single HumanMessage
            return [HumanMessage(content=input.to_string())]

    # 3) Single string => HumanMessage
    if isinstance(input, str):
        return [HumanMessage(content=input)]

    # 4) Single LC message
    if isinstance(input, BaseMessage):
        return [input]

    # 5) Single OpenAI-style dict
    if isinstance(input, dict):
        role = input.get("role")
        content = input.get("content", "")
        if role == "user":
            return [HumanMessage(content=content)]
        elif role == "assistant":
            return [AIMessage(content=content)]
        elif role == "system":
            return [SystemMessage(content=content)]
        else:
            raise ValueError(f"Unknown role: {role}")

    # 6) List inputs
    if isinstance(input, list):
        if not input:
            return []
        first = input[0]

        # Already LC messages
        if isinstance(first, BaseMessage):
            return input  # type: ignore[return-value]

        # OpenAI-style dicts
        if isinstance(first, dict):
            lc_messages: List[BaseMessage] = []
            for msg in input:  # type: ignore[assignment]
                role = msg.get("role")
                content = msg.get("content", "")
                if role == "user":
                    lc_messages.append(HumanMessage(content=content))
                elif role == "assistant":
                    lc_messages.append(AIMessage(content=content))
                elif role == "system":
                    lc_messages.append(SystemMessage(content=content))
                else:
                    raise ValueError(f"Unknown role: {role}")
            return lc_messages

    raise TypeError(f"Unsupported input type: {type(input)}")


def invoke(
    self,
    input: Union[
        List[BaseMessage],
        List[Dict[str, str]],
        BaseMessage,
        Dict[str, str],
        str,
    ],
    config: Optional[RunnableConfig] = None,
    **kwargs: Any,
) -> AIMessage:
    """Invoke the model in an LCEL-compatible way and return enriched AIMessage.

    This method accepts:
    - List[BaseMessage] (LangChain messages)
    - List[dict]        (OpenAI-style)
    - BaseMessage
    - dict              (with role/content)
    - str               (treated as a single HumanMessage)
    """
    # 1) Coerce input into a list of BaseMessage
    lc_messages: List[BaseMessage] = self._coerce_to_lc_messages(input)

    # 2) Optionally derive a run manager from config (safe to ignore if you don't use it)
    run_manager: Optional[CallbackManagerForLLMRun] = None
    if isinstance(config, dict):
        # LangChain sets callbacks into config; if you want to wire them in:
        try:
            run_manager = CallbackManagerForLLMRun.get_noop_manager()
        except Exception:
            run_manager = None

    # 3) Generate
    result: ChatResult = self._generate(
        messages=lc_messages, run_manager=run_manager, **kwargs
    )

    # Support both shapes of generations (List[ChatGen] vs List[List[ChatGen]])
    # generation = self._first_generation(result) # Commented out in source

    generation = result.generations[0]
    message = generation.message

    # Extract metadata
    llm_output = result.llm_output or {}
    token_usage = llm_output.get("token_usage", {})
    model_name = llm_output.get("model", "")
    system_fingerprint = llm_output.get("system_fingerprint", "")
    finish_reason = generation.generation_info.get("finish_reason")
    logprobs = generation.generation_info.get("logprobs")

    # Construct enriched AIMessage
    enriched_message = AIMessage(
        content=message.content,
        additional_kwargs=message.additional_kwargs,
        response_metadata={
            "token_usage": token_usage,
            "model_name": model_name,
            "system_fingerprint": system_fingerprint,
            "finish_reason": finish_reason,
            "logprobs": logprobs,
            "content_filter_results": {}
        },
        id=f"run-{uuid4()}-0",
        usage_metadata={
            "input_tokens": token_usage.get("prompt_tokens", 0),
            "output_tokens": token_usage.get("completion_tokens", 0),
            "total_tokens": token_usage.get("total_tokens", 0),
            "input_token_details": token_usage.get("prompt_tokens_details", {}),
            "output_token_details": token_usage.get("completion_tokens_details", {})
        }
    )

    return enriched_message
