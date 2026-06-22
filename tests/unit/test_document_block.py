"""Unit 069: first-class document content blocks."""

from __future__ import annotations

import base64

import pytest
from pydantic import TypeAdapter, ValidationError

from loopplane.host import DocumentBlock as HostDocumentBlock
from loopplane.model import DocumentBlock as ModelDocumentBlock
from loopplane.model.boundary import Message, ModelRequest
from loopplane.model.content import (
    ContentBlock,
    DocumentBlock,
    ImageBlock,
    OutputBlock,
    SummaryDigest,
    SummaryMarkerBlock,
    TextBlock,
    ToolCallBlock,
    ToolResultBlock,
)

_PDF_BYTES = b"%PDF-1.7\nminimal public test document\n%%EOF"
_PDF_MEDIA = base64.b64encode(_PDF_BYTES).decode("ascii")
_PDF_TYPE = "application/pdf"
_SAFE_NAME = "report.pdf"


def _join(*parts: str) -> str:
    return "".join(parts)


def _document(name: str | None = _SAFE_NAME) -> DocumentBlock:
    return DocumentBlock(media=_PDF_MEDIA, format=_PDF_TYPE, name=name)


def _round_trip_content(block: ContentBlock) -> ContentBlock:
    adapter = TypeAdapter(ContentBlock)
    return adapter.validate_json(adapter.dump_json(block))


def test_document_block_validates_and_round_trips() -> None:
    block = _document()

    restored = _round_trip_content(block)

    assert restored == block
    assert isinstance(restored, DocumentBlock)
    assert restored.kind == "document"
    assert restored.media == _PDF_MEDIA
    assert restored.format == _PDF_TYPE
    assert restored.name == _SAFE_NAME


def test_document_block_rejects_empty_media_and_format() -> None:
    with pytest.raises(ValidationError):
        DocumentBlock(media="", format=_PDF_TYPE)
    with pytest.raises(ValidationError):
        DocumentBlock(media=_PDF_MEDIA, format="")


def test_document_block_rejects_unsafe_display_names() -> None:
    unsafe_names = [
        _join("C", ":\\", "private\\", "report.pdf"),
        "../report.pdf",
        "nested/report.pdf",
        _join("sk", "-", "sec", "ret", "-report.pdf"),
        _join("api", "_key", "-report.pdf"),
        _join("pass", "word", "-report.pdf"),
        _join("tok", "en", "-report.pdf"),
    ]

    for name in unsafe_names:
        with pytest.raises(ValidationError):
            DocumentBlock(media=_PDF_MEDIA, format=_PDF_TYPE, name=name)


def test_document_block_is_content_not_tool_output() -> None:
    document = _document()

    assert TypeAdapter(ContentBlock).validate_python(document) == document
    with pytest.raises(ValidationError):
        TypeAdapter(OutputBlock).validate_python(document.model_dump(mode="json"))


def test_existing_content_blocks_round_trip_unchanged() -> None:
    blocks: list[ContentBlock] = [
        TextBlock(text="hello"),
        ImageBlock(media="aGVsbG8=", format="image/png"),
        ToolCallBlock(call_id="c1", tool_name="echo", input={"text": "x"}),
        ToolResultBlock(call_id="c1", outcome="success", outputs=[TextBlock(text="x")]),
        SummaryMarkerBlock(
            digest=SummaryDigest(turn_count=1, tool_names=["echo"], excerpts=["done"])
        ),
    ]

    assert [_round_trip_content(block) for block in blocks] == blocks


def test_model_request_preserves_document_order() -> None:
    document = _document()
    image = ImageBlock(media="aGVsbG8=", format="image/png")
    request = ModelRequest(
        context=[
            Message(
                role="user",
                blocks=[
                    TextBlock(text="read this"),
                    document,
                    image,
                    TextBlock(text="then compare"),
                ],
            )
        ]
    )

    restored = ModelRequest.model_validate(request.model_dump(mode="json"))

    assert restored.context[0].blocks == [
        TextBlock(text="read this"),
        document,
        image,
        TextBlock(text="then compare"),
    ]


def test_document_block_is_exported_from_public_model_and_host() -> None:
    assert ModelDocumentBlock is DocumentBlock
    assert HostDocumentBlock is DocumentBlock
