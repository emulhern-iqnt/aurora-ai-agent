from llama-index.llms.ollama import Ollama

llm: Ollama = Ollama(base_url="http://44.200.48.59:11434", model="llama3.2")
print(llm.complete("Tell me a joke"))