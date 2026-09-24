"""Create the Block 8 persistent research schema.

Revision ID: 20260924_0002
Revises: None
"""

from __future__ import annotations

from alembic import op

revision = "20260924_0002"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    _execute_statements(
        """
        CREATE TABLE research_runs (
          run_id VARCHAR(160) PRIMARY KEY,
          idempotency_key VARCHAR(200) NOT NULL UNIQUE,
          request_sha256 VARCHAR(64) NOT NULL,
          scenario VARCHAR(24) NOT NULL CONSTRAINT ck_runs_scenario
            CHECK (scenario IN ('valid', 'blocked')),
          state VARCHAR(32) NOT NULL CONSTRAINT ck_runs_state
            CHECK (state IN ('created', 'generated', 'validated', 'pending_review', 'finalized')),
          data_origin VARCHAR(80) NOT NULL CONSTRAINT ck_runs_data_origin
            CHECK (data_origin IN ('frozen_offline_fixture')),
          response_payload JSONB NOT NULL,
          created_at TIMESTAMPTZ NOT NULL
        );

        CREATE TABLE market_snapshots (
          snapshot_id VARCHAR(160) NOT NULL,
          run_id VARCHAR(160) NOT NULL REFERENCES research_runs(run_id) ON DELETE RESTRICT,
          provider VARCHAR(160) NOT NULL,
          content_sha256 VARCHAR(64) NOT NULL,
          artifact_uri TEXT NOT NULL,
          retrieved_at TIMESTAMPTZ NOT NULL,
          payload JSONB NOT NULL,
          PRIMARY KEY (snapshot_id, run_id),
          CONSTRAINT uq_snapshot_run_id UNIQUE (run_id, snapshot_id)
        );

        CREATE TABLE metric_records (
          metric_id VARCHAR(160) PRIMARY KEY,
          run_id VARCHAR(160) NOT NULL,
          snapshot_id VARCHAR(160) NOT NULL,
          metric_name VARCHAR(160) NOT NULL,
          value DOUBLE PRECISION NOT NULL,
          unit VARCHAR(200) NOT NULL,
          horizon_or_frequency VARCHAR(200) NOT NULL,
          formula_version VARCHAR(200) NOT NULL,
          CONSTRAINT fk_metric_snapshot_same_run FOREIGN KEY (run_id, snapshot_id)
            REFERENCES market_snapshots(run_id, snapshot_id) ON DELETE RESTRICT,
          CONSTRAINT uq_metric_run_id UNIQUE (run_id, metric_id)
        );

        CREATE TABLE source_documents (
          document_id VARCHAR(160) PRIMARY KEY,
          document_sha256 VARCHAR(64) NOT NULL,
          title TEXT NOT NULL,
          source_kind VARCHAR(80) NOT NULL CONSTRAINT ck_document_source_kind
            CHECK (source_kind IN ('synthetic_demo_evidence', 'official_corpus_passage')),
          metadata_payload JSONB NOT NULL,
          CONSTRAINT uq_document_identity_hash UNIQUE (document_id, document_sha256)
        );

        CREATE TABLE evidence_records (
          evidence_id VARCHAR(160) PRIMARY KEY,
          run_id VARCHAR(160) NOT NULL REFERENCES research_runs(run_id) ON DELETE RESTRICT,
          document_id VARCHAR(160) NOT NULL,
          document_sha256 VARCHAR(64) NOT NULL,
          status VARCHAR(80) NOT NULL CONSTRAINT ck_evidence_status
            CHECK (status IN ('synthetic_demo_evidence', 'official_corpus_passage')),
          payload JSONB NOT NULL,
          CONSTRAINT fk_evidence_document_hash FOREIGN KEY (document_id, document_sha256)
            REFERENCES source_documents(document_id, document_sha256) ON DELETE RESTRICT,
          CONSTRAINT uq_evidence_run_id UNIQUE (run_id, evidence_id)
        );

        CREATE TABLE generated_drafts (
          draft_id VARCHAR(160) PRIMARY KEY,
          run_id VARCHAR(160) NOT NULL REFERENCES research_runs(run_id) ON DELETE RESTRICT,
          version INTEGER NOT NULL CONSTRAINT ck_draft_version_positive CHECK (version > 0),
          summary TEXT NOT NULL,
          limitations JSONB NOT NULL,
          generation_payload JSONB NOT NULL,
          created_at TIMESTAMPTZ NOT NULL,
          CONSTRAINT uq_draft_run_version UNIQUE (run_id, version),
          CONSTRAINT uq_draft_run_id UNIQUE (run_id, draft_id),
          CONSTRAINT uq_draft_run_id_version UNIQUE (run_id, draft_id, version)
        );

        CREATE TABLE draft_claims (
          claim_id VARCHAR(160) PRIMARY KEY,
          run_id VARCHAR(160) NOT NULL,
          draft_id VARCHAR(160) NOT NULL,
          position INTEGER NOT NULL CONSTRAINT ck_claim_position_positive CHECK (position > 0),
          claim_type VARCHAR(32) NOT NULL CONSTRAINT ck_claim_type
            CHECK (claim_type IN ('quantitative', 'evidence', 'limitation')),
          text_template TEXT NOT NULL,
          declared_metric_ids JSONB NOT NULL
            CONSTRAINT ck_claim_declared_metric_ids_string_array CHECK (
              jsonb_typeof(declared_metric_ids) = 'array'
              AND jsonb_path_query_array(
                declared_metric_ids, '$[*] ? (@.type() == "string")'
              ) = declared_metric_ids
            ),
          declared_evidence_ids JSONB NOT NULL
            CONSTRAINT ck_claim_declared_evidence_ids_string_array CHECK (
              jsonb_typeof(declared_evidence_ids) = 'array'
              AND jsonb_path_query_array(
                declared_evidence_ids, '$[*] ? (@.type() == "string")'
              ) = declared_evidence_ids
            ),
          uncertainty TEXT,
          CONSTRAINT fk_claim_draft_same_run FOREIGN KEY (run_id, draft_id)
            REFERENCES generated_drafts(run_id, draft_id) ON DELETE RESTRICT,
          CONSTRAINT uq_claim_draft_position UNIQUE (draft_id, position),
          CONSTRAINT uq_claim_run_id UNIQUE (run_id, claim_id),
          CONSTRAINT uq_claim_run_draft_id UNIQUE (run_id, draft_id, claim_id)
        );

        CREATE TABLE draft_claim_metric_refs (
          run_id VARCHAR(160) NOT NULL,
          draft_id VARCHAR(160) NOT NULL,
          claim_id VARCHAR(160) NOT NULL,
          metric_id VARCHAR(160) NOT NULL,
          position INTEGER NOT NULL CONSTRAINT ck_claim_metric_ref_position_positive
            CHECK (position > 0),
          PRIMARY KEY (run_id, draft_id, claim_id, metric_id),
          CONSTRAINT fk_claim_metric_ref_claim_same_run
            FOREIGN KEY (run_id, draft_id, claim_id)
            REFERENCES draft_claims(run_id, draft_id, claim_id) ON DELETE RESTRICT,
          CONSTRAINT fk_claim_metric_ref_metric_same_run FOREIGN KEY (run_id, metric_id)
            REFERENCES metric_records(run_id, metric_id) ON DELETE RESTRICT,
          CONSTRAINT uq_claim_metric_ref_position
            UNIQUE (run_id, draft_id, claim_id, position)
        );

        CREATE TABLE draft_claim_evidence_refs (
          run_id VARCHAR(160) NOT NULL,
          draft_id VARCHAR(160) NOT NULL,
          claim_id VARCHAR(160) NOT NULL,
          evidence_id VARCHAR(160) NOT NULL,
          position INTEGER NOT NULL CONSTRAINT ck_claim_evidence_ref_position_positive
            CHECK (position > 0),
          PRIMARY KEY (run_id, draft_id, claim_id, evidence_id),
          CONSTRAINT fk_claim_evidence_ref_claim_same_run
            FOREIGN KEY (run_id, draft_id, claim_id)
            REFERENCES draft_claims(run_id, draft_id, claim_id) ON DELETE RESTRICT,
          CONSTRAINT fk_claim_evidence_ref_evidence_same_run FOREIGN KEY (run_id, evidence_id)
            REFERENCES evidence_records(run_id, evidence_id) ON DELETE RESTRICT,
          CONSTRAINT uq_claim_evidence_ref_position
            UNIQUE (run_id, draft_id, claim_id, position)
        );

        CREATE TABLE validation_issues (
          issue_id VARCHAR(200) PRIMARY KEY,
          run_id VARCHAR(160) NOT NULL,
          draft_id VARCHAR(160) NOT NULL,
          position INTEGER NOT NULL CONSTRAINT ck_issue_position_positive CHECK (position > 0),
          code VARCHAR(80) NOT NULL,
          severity VARCHAR(16) NOT NULL CONSTRAINT ck_issue_severity
            CHECK (severity IN ('info', 'warning', 'error', 'critical')),
          claim_id VARCHAR(160),
          message TEXT NOT NULL,
          CONSTRAINT ck_issue_code CHECK (code IN (
            'unknown_metric', 'unknown_evidence', 'cross_run_reference',
            'free_numeric_literal', 'metric_value_literal',
            'evidence_numeric_literal_unverified', 'metric_placeholder_mismatch',
            'evidence_reference_mismatch', 'generic_placeholder', 'summary_placeholder',
            'unresolved_placeholder', 'unsupported_risk_statement',
            'unsupported_period_alignment', 'implicit_cross_domain_relation',
            'internal_status_token', 'reference_value_mismatch',
            'reference_claim_key_mismatch', 'reference_unit_mismatch',
            'reference_period_mismatch', 'scope2_method_mismatch', 'document_after_cutoff',
            'contradictory_source', 'missing_required_field', 'insufficient_coverage',
            'document_prompt_injection', 'self_approval_attempt',
            'insufficient_trusted_inputs'
          )),
          CONSTRAINT fk_issue_draft_same_run FOREIGN KEY (run_id, draft_id)
            REFERENCES generated_drafts(run_id, draft_id) ON DELETE RESTRICT,
          CONSTRAINT fk_issue_claim_same_draft FOREIGN KEY (run_id, draft_id, claim_id)
            REFERENCES draft_claims(run_id, draft_id, claim_id) ON DELETE RESTRICT,
          CONSTRAINT uq_issue_draft_position UNIQUE (draft_id, position)
        );

        CREATE TABLE automated_assessments (
          assessment_id VARCHAR(200) PRIMARY KEY,
          run_id VARCHAR(160) NOT NULL,
          draft_id VARCHAR(160) NOT NULL,
          status VARCHAR(32) NOT NULL CONSTRAINT ck_assessment_status
            CHECK (status IN ('eligible_for_review', 'review_required', 'abstain')),
          reason_codes JSONB NOT NULL CONSTRAINT ck_assessment_status_reason_exact CHECK (
            (status = 'eligible_for_review'
              AND reason_codes = '["validated_references"]'::jsonb)
            OR (status = 'review_required'
              AND reason_codes = '["blocking_validation_issues"]'::jsonb)
            OR (status = 'abstain'
              AND reason_codes = '["insufficient_trusted_inputs"]'::jsonb)
          ),
          created_at TIMESTAMPTZ NOT NULL,
          CONSTRAINT fk_assessment_draft_same_run FOREIGN KEY (run_id, draft_id)
            REFERENCES generated_drafts(run_id, draft_id) ON DELETE RESTRICT,
          CONSTRAINT uq_assessment_draft UNIQUE (draft_id)
        );

        CREATE TABLE human_reviews (
          review_id VARCHAR(200) PRIMARY KEY,
          run_id VARCHAR(160) NOT NULL,
          draft_id VARCHAR(160) NOT NULL,
          draft_version INTEGER NOT NULL CONSTRAINT ck_review_version_positive
            CHECK (draft_version > 0),
          reviewer_entered VARCHAR(200) NOT NULL CONSTRAINT ck_reviewer_nonblank
            CHECK (btrim(reviewer_entered) <> ''),
          disposition VARCHAR(32) NOT NULL CONSTRAINT ck_review_disposition
            CHECK (disposition IN ('approved', 'corrected', 'rejected', 'escalated')),
          comment TEXT NOT NULL CONSTRAINT ck_review_comment_nonblank CHECK (btrim(comment) <> ''),
          reviewed_at TIMESTAMPTZ NOT NULL,
          CONSTRAINT fk_review_draft_same_run_version
            FOREIGN KEY (run_id, draft_id, draft_version)
            REFERENCES generated_drafts(run_id, draft_id, version) ON DELETE RESTRICT
        );
        CREATE INDEX ix_reviews_run_created ON human_reviews (run_id, reviewed_at);

        CREATE TABLE model_calls (
          call_id VARCHAR(200) PRIMARY KEY,
          run_id VARCHAR(160) NOT NULL,
          draft_id VARCHAR(160) NOT NULL,
          provider VARCHAR(160) NOT NULL,
          model_id VARCHAR(200) NOT NULL,
          status VARCHAR(32) NOT NULL CONSTRAINT ck_model_call_status CHECK (
            status IN ('success', 'provider_error', 'timeout', 'schema_error', 'allowlist_error')
          ),
          response_origin VARCHAR(64) NOT NULL CONSTRAINT ck_model_call_response_origin CHECK (
            response_origin IN (
              'deterministic_fake', 'synthetic_offline_fixture',
              'mocked_provider', 'live_provider'
            )
          ),
          payload JSONB NOT NULL,
          CONSTRAINT fk_model_call_draft_same_run FOREIGN KEY (run_id, draft_id)
            REFERENCES generated_drafts(run_id, draft_id) ON DELETE RESTRICT
        );

        CREATE TABLE evaluation_runs (
          evaluation_id VARCHAR(200) PRIMARY KEY,
          schema_version VARCHAR(80) NOT NULL,
          dataset_sha256 VARCHAR(64) NOT NULL,
          case_count INTEGER NOT NULL CONSTRAINT ck_evaluation_case_count_positive
            CHECK (case_count > 0),
          report_payload JSONB NOT NULL,
          created_at TIMESTAMPTZ NOT NULL,
          CONSTRAINT uq_evaluation_dataset UNIQUE (schema_version, dataset_sha256)
        );
        """
    )


def downgrade() -> None:
    _execute_statements(
        """
        DROP TABLE IF EXISTS evaluation_runs;
        DROP TABLE IF EXISTS model_calls;
        DROP TABLE IF EXISTS human_reviews;
        DROP TABLE IF EXISTS automated_assessments;
        DROP TABLE IF EXISTS validation_issues;
        DROP TABLE IF EXISTS draft_claim_evidence_refs;
        DROP TABLE IF EXISTS draft_claim_metric_refs;
        DROP TABLE IF EXISTS draft_claims;
        DROP TABLE IF EXISTS generated_drafts;
        DROP TABLE IF EXISTS evidence_records;
        DROP TABLE IF EXISTS source_documents;
        DROP TABLE IF EXISTS metric_records;
        DROP TABLE IF EXISTS market_snapshots;
        DROP TABLE IF EXISTS research_runs;
        """
    )


def _execute_statements(ddl: str) -> None:
    """Execute one statement at a time for psycopg prepared-statement compatibility."""

    for statement in ddl.split(";"):
        if statement.strip():
            op.execute(statement)
