from llama_index.core import VectorStoreIndex, StorageContext
from llama_index.core import Document
from llama_index.llms.litellm import LiteLLM
from llama_index.embeddings.litellm import LiteLLMEmbedding
from llama_index.core.readers.json import JSONReader
from llama_index.vector_stores.opensearch import OpensearchVectorStore
from llama_index.vector_stores.opensearch import OpensearchVectorClient


'''
the opensearch index must be mapped like this

index_body = {
    "settings": {
        "index": {
            "knn": True,
            "knn.algo_param.ef_search": 100  # Tune for search efficiency
        }
    },
    "mappings": {
        "properties": {
            "content": {"type": "text"},  # Text field for document content
            "embedding": {  # Vector field
                "type": "knn_vector",
                "dimension": 768,  # Match your embedding model's output dim
                "method": {
                    "name": "hnsw",
                    "space_type": "cosinesimil",  # Or "l2", "innerproduct"
                    # "engine": "nmslib",  # Or "faiss"
                    "parameters": {"ef_construction": 128, "m": 24}
                }
            }
        }
    }
}
'''


OPEN_SEARCH_ENDPOINT: str = "http://opensearch.inteliquent.com:9200"
OPEN_SEARCH_INDEX: str = "opensearch_dashboards_sample_data_logs"

llm: LiteLLM = LiteLLM(
    api_base="http://localhost:8000",
    api_key="XXXXXX",
    model="openai/llama3.3:latest"
)

# PROBABLYNeed to run:
# socat TCP-LISTEN:8000,fork,reuseaddr OPENSSL:aigateway.inteliquent.com:443,verify=0
# In order to get this working
embedding: LiteLLMEmbedding = LiteLLMEmbedding(
    api_base="http://localhost:8000",
    api_key="sk-B-KCtMPQ6mlr9yKA-O4BPw",
    model_name="openai/nomic-embed-text:latest"
)

reader: JSONReader = JSONReader(is_jsonl=True)
documents: list[Document] = reader.load_data(input_file="input_data_bak.jsonl")


os_client: OpensearchVectorClient = OpensearchVectorClient(
    endpoint=OPEN_SEARCH_ENDPOINT,
    index=OPEN_SEARCH_INDEX,
    dim=768
)

vector_store: OpensearchVectorStore = OpensearchVectorStore(client=os_client)
storage_context: StorageContext = StorageContext.from_defaults(vector_store=vector_store)
index: VectorStoreIndex = VectorStoreIndex.from_documents(
    documents=documents,
    embed_model=embedding,
    storage_context=storage_context,
    show_progress=True
)
