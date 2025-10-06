from llama_index.core import StorageContext
from llama_index.core import VectorStoreIndex
from llama_index.core.indices.base import BaseIndex
from llama_index.llms.litellm import LiteLLM
from llama_index.embeddings.litellm import LiteLLMEmbedding
from llama_index.core.query_engine import BaseQueryEngine
from llama_index.vector_stores.opensearch import OpensearchVectorStore
from llama_index.vector_stores.opensearch import OpensearchVectorClient


OPEN_SEARCH_ENDPOINT: str = "http://opensearch.inteliquent.com:9200"
OPEN_SEARCH_INDEX: str = "opensearch_dashboards_sample_data_logs"


llm: LiteLLM = LiteLLM(
    api_base="http://localhost:8000",
    api_key="XXXXXXX",
    #model="openai/llama3.3:latest",
    model="openai/llama3.1:8b",
)


embedding: LiteLLMEmbedding = LiteLLMEmbedding(
    api_base="http://localhost:8000",
    api_key="XXXXX",
    model_name="openai/nomic-embed-text:latest"
)


os_client: OpensearchVectorClient = OpensearchVectorClient(
    endpoint=OPEN_SEARCH_ENDPOINT,
    index=OPEN_SEARCH_INDEX,
    dim=768
)

vector_store: OpensearchVectorStore = OpensearchVectorStore(client=os_client)
storage_context: StorageContext = StorageContext.from_defaults(vector_store=vector_store)

index: BaseIndex = VectorStoreIndex.from_vector_store(
    vector_store=vector_store,
    storage_context=storage_context,
    embed_model=embedding
)

query_engine: BaseQueryEngine = index.as_query_engine(llm=llm)
response = query_engine.query(f"State me a fact from the source material")
print(response)
