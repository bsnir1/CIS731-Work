import deal
import pytest
import hashlib
from typing import Dict, Any, List

# Define specific validation exceptions
class ProvenanceError(Exception): pass
class ValidationError(Exception): pass

# Mock internal state for registry, index, and ID mappings
ADMITTED_DOCS: Dict[str, Dict[str, Any]] = {}
VDB_INDEX: Dict[str, List[float]] = {}
ID_MAP: Dict[str, int] = {}

# Invariant: A document enters the corpus only with an allowed license and a verified hash
@deal.pre(lambda doc: doc.get("license_class") in ["CC-BY-4.0", "CC-BY-SA-4.0", "CC0-1.0"])
@deal.pre(lambda doc: "source_hash" in doc)
@deal.post(lambda result: result["doc_id"] in ADMITTED_DOCS)
@deal.raises(ProvenanceError)
def admit_document(doc: Dict[str, Any]) -> Dict[str, Any]:
    # Mocking the SHA-256 verification step (would normally check the file contents)
    # The source_hash in the record must match the verified hash
    doc["provenance_verified"] = True
    ADMITTED_DOCS[doc["doc_id"]] = doc
    return doc

# Invariant: A chunk is stored once, with one vector, and only if its document was admitted
@deal.pre(lambda chunk: chunk.get("doc_id") in ADMITTED_DOCS, message="Document not admitted")
@deal.pre(lambda chunk: len(chunk.get("vector", [])) == chunk.get("embedding_dim", 37), message="Invalid vector dimensions")
@deal.pre(lambda chunk: abs(sum(v**2 for v in chunk.get("vector", [])) - 1.0) < 1e-6, message="Vector is not L2-normalized")
@deal.pre(lambda chunk: chunk.get("offset_end_sec", 0) - chunk.get("offset_start_sec", 0) <= 30, message="Window exceeds 30 seconds")
@deal.pre(lambda chunk: chunk["chunk_id"].startswith(f"{chunk['doc_id']}:{chunk['annotator']}:w"), message="chunk_id does not match properties")
@deal.ensure(lambda chunk, result: chunk["chunk_id"] in ID_MAP)
@deal.ensure(lambda chunk, result: str(ID_MAP[chunk["chunk_id"]]) in VDB_INDEX)
@deal.raises(ValidationError)
def vdb_upsert(chunk: Dict[str, Any]) -> bool:
    cid = chunk["chunk_id"]
    
    # Contract: Update ID Map
    if cid not in ID_MAP:
        new_id = len(ID_MAP) + 1
        ID_MAP[cid] = new_id
        
    # Contract: Update Mock VDB
    VDB_INDEX[str(ID_MAP[cid])] = chunk["vector"]
    return True

# --- Tests for the specific edge cases requested ---

def test_unlicensed_document():
    doc = {
        "doc_id": "vocadito_1",
        "license_class": "All Rights Reserved",
        "source_hash": hashlib.sha256(b"fake").hexdigest()
    }
    with pytest.raises(deal.PreContractError):
        admit_document(doc)

def test_orphan_vector():
    # Attempting to upsert a chunk whose document was never admitted
    chunk = {
        "chunk_id": "vocadito_1:A1:w0000",
        "doc_id": "vocadito_1",
        "annotator": "A1",
        "embedding_dim": 37,
        "vector": [1.0 / (37**0.5)] * 37, # L2-normalized 
        "offset_start_sec": 0.0,
        "offset_end_sec": 10.0
    }
    with pytest.raises(deal.PreContractError, match="Document not admitted"):
        vdb_upsert(chunk)

def test_duplicate_chunk_id():
    # Admit a valid doc to clear the first precondition
    admit_document({
        "doc_id": "vocadito_1",
        "license_class": "CC-BY-4.0",
        "source_hash": hashlib.sha256(b"fake").hexdigest()
    })
    
    chunk = {
        "chunk_id": "vocadito_1:A1:w0000",
        "doc_id": "vocadito_1",
        "annotator": "A1",
        "embedding_dim": 37,
        "vector": [1.0 / (37**0.5)] * 37,
        "offset_start_sec": 0.0,
        "offset_end_sec": 10.0
    }
    
    # First upsert succeeds
    vdb_upsert(chunk)
    first_id = ID_MAP[chunk["chunk_id"]]
    
    # Second upsert behaves as a simulated ID map update instead of duplicating
    vdb_upsert(chunk)
    assert ID_MAP[chunk["chunk_id"]] == first_id 
    assert str(first_id) in VDB_INDEX