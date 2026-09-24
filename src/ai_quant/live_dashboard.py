"""Streamlit-to-FastAPI adapter used only when APP_MODE=live."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
import uuid
from typing import Any

import streamlit as st


class PublicApiError(RuntimeError):
    """Clean user-facing API failure with no transport internals."""


def api_request(
    base_url: str,
    method: str,
    path: str,
    *,
    payload: dict[str, object] | None = None,
    headers: dict[str, str] | None = None,
) -> dict[str, Any] | list[dict[str, Any]]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request_headers = {"Accept": "application/json", **(headers or {})}
    if data is not None:
        request_headers["Content-Type"] = "application/json"
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}{path}",
        data=data,
        headers=request_headers,
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:  # noqa: S310
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        try:
            body = json.loads(error.read().decode("utf-8"))
            message = body["error"]["message"]
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            message = "The local API rejected the request."
        raise PublicApiError(message) from None
    except (urllib.error.URLError, TimeoutError):
        raise PublicApiError("The local API is unavailable.") from None


def render_live_dashboard(base_url: str) -> None:
    """Render persistent local controls without direct SQLAlchemy access."""

    st.header("Local persistent mode")
    st.info(
        "APP_MODE=live uses FastAPI and PostgreSQL. The current MVP still runs the explicitly "
        "labelled frozen offline fixture; it is not live market data and makes no provider call."
    )
    st.warning(
        "Reviewer names are entered text only. Identity is unverified and unauthenticated."
    )
    try:
        health = api_request(base_url, "GET", "/health")
        st.success(f"API health: {health['status']} · database: {health['database']}")
    except PublicApiError as error:
        st.error(str(error))
        return

    if "block8-idempotency-key" not in st.session_state:
        st.session_state["block8-idempotency-key"] = f"streamlit-{uuid.uuid4().hex}"
    scenario = st.selectbox("Persistent scenario", ("valid", "blocked"))
    idempotency_key = st.text_input(
        "Idempotency key",
        value=st.session_state["block8-idempotency-key"],
        help="Reuse with the same payload returns the same analysis; a different payload conflicts.",
    )
    if st.button("Run and persist analysis"):
        try:
            analysis = api_request(
                base_url,
                "POST",
                "/analyses",
                payload={"scenario": scenario, "data_mode": "frozen_offline_fixture"},
                headers={"Idempotency-Key": idempotency_key},
            )
            st.session_state["block8-live-analysis"] = analysis
        except PublicApiError as error:
            st.error(str(error))

    analysis = st.session_state.get("block8-live-analysis")
    if not isinstance(analysis, dict):
        return
    st.subheader("Persisted analysis")
    st.json(analysis)
    try:
        evidence = api_request(
            base_url, "GET", f"/analyses/{analysis['analysis_id']}/evidence"
        )
        st.subheader("Persisted evidence")
        st.json(evidence)
    except PublicApiError as error:
        st.error(str(error))

    st.subheader("Append-only review")
    with st.form("block8-persistent-review"):
        reviewer = st.text_input("Reviewer (entered, unverified, unauthenticated)")
        disposition = st.selectbox(
            "Disposition", ("approved", "corrected", "rejected", "escalated")
        )
        comment = st.text_input("Comment")
        corrected_summary = st.text_area(
            "Corrected summary (required only for corrected)",
            value=str(analysis.get("summary", "")),
        )
        corrected_claims = tuple(
            st.text_area(
                f"Corrected claim {index}", value=str(claim), key=f"live-claim-{index}"
            )
            for index, claim in enumerate(analysis.get("claims", ()), start=1)
        )
        submitted = st.form_submit_button("Append review")
    if submitted:
        try:
            review = api_request(
                base_url,
                "POST",
                f"/analyses/{analysis['analysis_id']}/reviews",
                payload={
                    "draft_id": analysis["draft_id"],
                    "draft_version": analysis["draft_version"],
                    "reviewer": reviewer,
                    "disposition": disposition,
                    "comment": comment,
                    **(
                        {
                            "corrected_summary": corrected_summary,
                            "corrected_claims": corrected_claims,
                        }
                        if disposition == "corrected"
                        else {}
                    ),
                },
            )
            st.success("A new review row was appended; no historical row was changed.")
            st.json(review)
            if review.get("resulting_draft_id"):
                st.session_state["block8-live-analysis"] = api_request(
                    base_url, "GET", f"/analyses/{analysis['analysis_id']}"
                )
        except PublicApiError as error:
            st.error(str(error))
