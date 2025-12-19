import os
from typing import Iterator
from dotenv import load_dotenv
from groq import Groq
from .base import LLMClient
from .config import LLMConfig

# TODO 1: load dotenv
load_dotenv()

class GroqClient(LLMClient):
    def __init__(self, config: LLMConfig):
        super().__init__(config)
        # TODO 2: create groq client and set api_key from .env
        self.client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
    
    def generate(self, messages: list[dict[str, str]], tools = None) -> dict:
        # TODO: write description for Returend Fields 
        """ Main Returned Dict Fields
            - content: The assistant's response text/message
            - role: The message role (always 'assistant' for responses)
            - tool_calls: Optional list of tool calls the model wants to execute
            - stop_reason: Why generation stopped ('end_turn', 'tool_calls', etc)
        """
        
        # TODO 3: call `client.chat.completions.create` with configurations in self.config
        # TODO 3: search difference between max_tokens and max_compeletion_tokens
        # TODO 3: now you can pass tools=tools but search about format later when move to tools sections

        response = self.client.chat.completions.create(
            model=self.config.model_name,           # Use model name from config
            messages=messages,                       # Pass conversation history
            temperature=self.config.temperature,    # Control randomness
            top_p=self.config.top_p,                # Control diversity
            max_tokens=self.config.max_tokens,      # Limit response length
            tools=tools,                             # Optional tool definitions
            reasoning_effort=self.config.reasoning_effort  # Set reasoning effort
    )

        return response.choices[0].message.model_dump()
    
    def stream(self, messages: list[dict[str, str]], tools = None) -> Iterator[dict]:
        # TODO 3: call `client.chat.completions.create` with stream options configurations in self.config
        
        stream = self.client.chat.completions.create(
            model=self.config.model_name,
            messages=messages,
            temperature=self.config.temperature,
            top_p=self.config.top_p,
            max_tokens=self.config.max_tokens,
            stream=True,
            tools=tools
        )

        for chunk in stream:
            yield chunk.choices[0].delta.model_dump()
                
                
if __name__ == "__main__":
    #TODO: initlaize configuraiton with reasoning model -- search for groq reasoning models 
    config = LLMConfig(
        model_name="openai/gpt-oss-120b", 
        max_tokens=5000,                    
        temperature=1.0,                    
        top_p=1.0,                          
        reasoning_effort="medium"           
    )
    client = GroqClient(config)
    
    #TODO: write messages with (1. system prompt on how the model is QA engineer and know python, playwright etc... provide in course) 
    #TODO: (2. Ask model to "write a plan to build a software autonomus like cursor but for testing") 
    messages = [
        {
            "role": "system", 
            "content": """You are a highly skilled QA Automation Engineer with expertise in:
- Python programming and unit testing
- Test automation frameworks like Playwright and HuggingFace
- Writing clear, maintainable, and efficient test scripts
- Software testing best practices
- Software architecture and design patterns

Your task is to provide detailed, practical, and well-structured responses.""",
        },
        {
            "role": "user", 
            "content": "Write a detailed plan to build a software autonomous agent like Cursor but for testing. Include architecture, components, and implementation steps."   
        }
    ]
    
    #TODO: test client.generate
    print("TESTING client.generate() - Full Response")
    response = client.generate(messages)
    print(f"Response: {response.get('content', '')}\n")

    #TODO: test client.stream and mention what's difference and why we need it?
    print("TESTING client.stream() - Streaming Response")
    for chunk in client.stream(messages):
        print(chunk.get('content', ''), end='', flush=True)
    print("\n")

    #Difference between generate and stream:
    # - generate: waits for full response before returning
    # - stream: yields response token by token as they are generated, we need it for real-time applications especially for long responses
    
    #TODO add the new answer to messages -> create multi-turn conversation (with same system message from above)
        # user: your name is CHATTAH tester
        # assisstant: ...
        # user: tell me what's your name and what are language you expert in it ?
    messages = [
        messages[0],
        {"role": "user", "content": "your name is CHATTAH tester"},        
    ]
    # TODO: first turn -> get answer -> print answer -> append answer to messages "i.e state"
    print("\nFirst Turn - Setting identity:")
    print("User: Your name is CHATTAH tester")
    answer = client.generate(messages)
    print(f"Assistant: {answer.get('content', '')}")

    # Append assistant's response to messages (building conversation state)
    messages.append({
        "role": "assistant",
        "content": answer.get('content', '')
    })

    # TODO: second turn -> get answer -> print answer -> append answer to messages "i.e state"
    messages.append({
        "role": "user", 
        "content": "Tell me what's your name and what are the languages you are expert in?"
    })

    print("\nSecond Turn - Asking about expertise:")
    print("User: Tell me what's your name and what are the languages you are expert in?")
    answer = client.generate(messages)
    print(f"Assistant: {answer.get('content', '')}")
    
    # Append assistant's response to messages (completing the conversation state)
    messages.append({
        "role": "assistant",
        "content": answer.get('content', '')
    })

    print("Conversation State (all messages):")
    for msg in messages:
        print(f"{msg['role'].upper()}: {msg['content'][:100]}...")