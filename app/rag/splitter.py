from typing import List
from langchain_text_splitters import RecursiveCharacterTextSplitter


def split_texts(texts: List[str], chunk_size: int = 1000, chunk_overlap: int = 150) -> List[str]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )
    return splitter.split_text("\n\n".join(texts))
