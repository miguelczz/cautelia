// GENERADO. No editar a mano.
//
// Sale del catalogo de textos (`app/config/copy/`) con el comando
// `mise run contracts:gen`. El guion de verificacion lo regenera y compara: si
// el catalogo cambio y este archivo no, la compuerta falla con su nombre.
//
// Una clave que no existe es un error de tipos aqui, no un texto vacio en
// pantalla.

/** Toda clave del catalogo que la interfaz resuelve, en los dos idiomas. */
export type CopyKey =
  | "action.back_to_conversation"
  | "action.go_home"
  | "action.retry"
  | "action.start_over"
  | "adjuster.panel.ai_notice"
  | "adjuster.panel.capped"
  | "adjuster.panel.decided"
  | "adjuster.panel.decision"
  | "adjuster.panel.failed"
  | "adjuster.panel.running"
  | "adjuster.panel.sources"
  | "adjuster.panel.steps"
  | "adjuster.panel.title"
  | "adjuster.panel.title_pending"
  | "adjuster.source.kind.clause"
  | "adjuster.source.kind.web"
  | "adjuster.source.new_tab"
  | "adjuster.source.rule"
  | "adjuster.step.case_read.title"
  | "adjuster.step.clauses.title"
  | "adjuster.step.decision.title"
  | "adjuster.step.policy_read.title"
  | "adjuster.step.rules.title"
  | "adjuster.step.vehicle_value.title"
  | "case.channel.chat"
  | "case.channel.voice"
  | "case.derivation_reason.demo_limit"
  | "case.derivation_reason.person_requested"
  | "case.derivation_reason.rule"
  | "case.field.annual_mileage_band"
  | "case.field.at_fault_losses_3y"
  | "case.field.claims_3y"
  | "case.field.description"
  | "case.field.driver_birth_date"
  | "case.field.driver_name"
  | "case.field.garaging_jurisdiction"
  | "case.field.identity_and_policy"
  | "case.field.incident_datetime"
  | "case.field.injuries"
  | "case.field.lapse_months"
  | "case.field.license_jurisdiction"
  | "case.field.license_years"
  | "case.field.location"
  | "case.field.other_parties"
  | "case.field.prior_coverage_active"
  | "case.field.question_asked"
  | "case.field.salvage_title"
  | "case.field.use_type"
  | "case.field.vehicle_age_years"
  | "case.field.vehicle_and_driver"
  | "case.field.vehicle_make"
  | "case.field.vehicle_model"
  | "case.field.vehicle_year"
  | "case.field.vin"
  | "case.field_unavailable"
  | "case.record_type.claim"
  | "case.record_type.coverage_inquiry"
  | "case.record_type.quote_request"
  | "case.resolution.approved"
  | "case.resolution.registered"
  | "case.resolution.rejected"
  | "case.resolution.sent_to_insurer"
  | "case.state.awaiting_insured"
  | "case.state.capturing"
  | "case.state.closed"
  | "case.state.deciding"
  | "case.state.derived"
  | "case.state.open"
  | "case.state.verifying"
  | "cases.example.back"
  | "cases.example.note"
  | "cases.example.title"
  | "cases.examples.empty"
  | "cases.examples.hint"
  | "cases.examples.insurer_label"
  | "cases.examples.title"
  | "cases.group.awaiting_insured"
  | "cases.group.capturing"
  | "cases.group.closed"
  | "cases.group.deciding"
  | "cases.group.derived"
  | "cases.group.verifying"
  | "cases.intro"
  | "cases.mine.chat"
  | "cases.mine.chat_with"
  | "cases.mine.empty"
  | "cases.mine.hint"
  | "cases.mine.number"
  | "cases.mine.title"
  | "cases.mine.view"
  | "cases.mine.view_of"
  | "cases.nav"
  | "cases.start"
  | "cases.title"
  | "chat.chip.add_more"
  | "chat.chip.adjuster_review"
  | "chat.chip.another_question"
  | "chat.chip.answer_no"
  | "chat.chip.answer_yes"
  | "chat.chip.example_holder"
  | "chat.chip.example_policy"
  | "chat.chip.leave_it"
  | "chat.chip.mileage_high"
  | "chat.chip.mileage_low"
  | "chat.chip.mileage_medium"
  | "chat.chip.nobody_hurt"
  | "chat.chip.policy_question"
  | "chat.chip.quote"
  | "chat.chip.report"
  | "chat.chip.someone_hurt"
  | "chat.chip.today"
  | "chat.chip.use_commercial"
  | "chat.chip.use_commuting"
  | "chat.chip.use_personal"
  | "chat.chip.yesterday"
  | "chat.citation.amount_deferred"
  | "chat.citation.expand"
  | "chat.citation.hide_original"
  | "chat.citation.language_en"
  | "chat.citation.language_es"
  | "chat.citation.other_language"
  | "chat.citation.position"
  | "chat.citation.reference"
  | "chat.citation.show_original"
  | "chat.citation.special_condition"
  | "chat.citation.trace_link"
  | "chat.citation.translation_note"
  | "chat.greeting.hello"
  | "chat.limit.rate"
  | "chat.limit.site_day"
  | "chat.limit.size"
  | "chat.opening.capabilities"
  | "chat.opening.capabilities_with_quote"
  | "chat.opening.disclosure"
  | "chat.page.answering_in"
  | "chat.page.case_complete"
  | "chat.page.case_kind_claim"
  | "chat.page.case_kind_inquiry"
  | "chat.page.case_kind_other"
  | "chat.page.case_kind_quote"
  | "chat.page.case_link"
  | "chat.page.case_missing_many"
  | "chat.page.case_missing_one"
  | "chat.page.case_number"
  | "chat.page.composer_hint"
  | "chat.page.composer_label"
  | "chat.page.connecting"
  | "chat.page.history_restored"
  | "chat.page.reset"
  | "chat.page.reset_body"
  | "chat.page.reset_body_with_case"
  | "chat.page.reset_cancel"
  | "chat.page.reset_confirm"
  | "chat.page.reset_title"
  | "chat.page.reviewing"
  | "chat.page.see_reasoning"
  | "chat.page.send"
  | "chat.page.speaker_visitor"
  | "chat.page.speaking_in"
  | "chat.page.title"
  | "chat.page.transcript_label"
  | "chat.page.typing"
  | "chat.reasoning.adjuster_decides"
  | "chat.reasoning.clause_not_verified"
  | "chat.reasoning.clause_verified"
  | "chat.reasoning.empty"
  | "chat.reasoning.missing"
  | "chat.reasoning.noted"
  | "chat.reasoning.optional"
  | "chat.reasoning.outcome_no_clause"
  | "chat.reasoning.outcome_rejected"
  | "chat.reasoning.outcome_unverifiable"
  | "chat.reasoning.outcome_verified"
  | "chat.reasoning.policy_confirmed"
  | "chat.reasoning.policy_missing"
  | "chat.reasoning.state_closed"
  | "chat.reasoning.state_derived"
  | "chat.reasoning.state_open"
  | "chat.reasoning.step_checked"
  | "chat.reasoning.step_next"
  | "chat.reasoning.step_noted"
  | "chat.reasoning.step_policy"
  | "chat.reasoning.step_understood"
  | "chat.reasoning.title"
  | "chat.reasoning.wants_claim"
  | "chat.reasoning.wants_question"
  | "chat.reasoning.wants_quote"
  | "chat.reasoning.you_asked"
  | "chat.turn.error"
  | "chat.turn.waiting"
  | "comparison.asked.label"
  | "comparison.asked.meta"
  | "comparison.asked.new"
  | "comparison.column.failed"
  | "comparison.column.idle"
  | "comparison.column.interrupted"
  | "comparison.column.loading"
  | "comparison.column.policy"
  | "comparison.column.policy_issued_by"
  | "comparison.column.rejected_title"
  | "comparison.column.retry"
  | "comparison.composer.label"
  | "comparison.composer.send"
  | "comparison.disclosure.assistant"
  | "comparison.disclosure.demo"
  | "comparison.disclosure.incomplete"
  | "comparison.examples.blown_tire"
  | "comparison.examples.hail"
  | "comparison.examples.lend_car"
  | "comparison.examples.other_driver_no_insurance"
  | "comparison.examples.passenger_medical"
  | "comparison.examples.rental_car"
  | "comparison.examples.ride_app"
  | "comparison.examples.stolen_keys"
  | "comparison.examples.title"
  | "comparison.out_of_scope.chat_link"
  | "comparison.out_of_scope.explanation"
  | "comparison.page.lead"
  | "comparison.page.loading"
  | "comparison.page.title"
  | "comparison.state.answered"
  | "comparison.state.failed"
  | "comparison.state.interrupted"
  | "comparison.state.loading"
  | "comparison.state.rejected"
  | "compliance.closure.direct"
  | "compliance.emergency.local"
  | "compliance.emergency.public"
  | "compliance.guard.amount"
  | "compliance.guard.config_disclosure"
  | "compliance.guard.coverage_promise"
  | "compliance.guard.degraded"
  | "compliance.guard.fault"
  | "compliance.guard.legal_advice"
  | "compliance.guard.transfer_or_deadline"
  | "compliance.handoff.adjuster_review"
  | "compliance.handoff.adjuster_review_inquiry"
  | "demo.notice.label"
  | "demo.notice.less"
  | "demo.notice.more"
  | "demo.reset.conversation_notice"
  | "demo.reset.surfaces_closed"
  | "documents.amended_by"
  | "documents.cited"
  | "documents.clause_count"
  | "documents.close"
  | "documents.how"
  | "documents.kind_base"
  | "documents.kind_endorsement"
  | "documents.kind_jurisdiction"
  | "documents.list_label"
  | "documents.loading"
  | "documents.no_match"
  | "documents.not_in_force"
  | "documents.not_in_force_why"
  | "documents.open"
  | "documents.search_label"
  | "documents.show_original"
  | "documents.show_translation"
  | "documents.static"
  | "documents.title"
  | "documents.translation_note"
  | "evals.scripted_insured.unknown_field"
  | "guide.about.limit"
  | "guide.about.sample"
  | "guide.about.what"
  | "guide.differences.agent"
  | "guide.differences.same"
  | "guide.differences.tip"
  | "guide.differences.title"
  | "guide.start"
  | "guide.steps.adjuster.body"
  | "guide.steps.adjuster.title"
  | "guide.steps.choose.body"
  | "guide.steps.choose.title"
  | "guide.steps.link.body"
  | "guide.steps.link.title"
  | "guide.steps.report.both"
  | "guide.steps.report.chat"
  | "guide.steps.report.policy"
  | "guide.steps.report.title"
  | "guide.steps.report.voice"
  | "guide.steps.title"
  | "guide.title"
  | "guide.try.ask_coverage"
  | "guide.try.cases"
  | "guide.try.compare"
  | "guide.try.interrupt"
  | "guide.try.telemetry"
  | "guide.try.title"
  | "home.action.chat"
  | "home.action.chat_with"
  | "home.action.policies"
  | "home.action.policies_of"
  | "home.action.voice"
  | "home.action.voice_with"
  | "home.demo_line"
  | "home.how.report_both"
  | "home.how.report_chat"
  | "home.how.report_voice"
  | "home.how.title"
  | "home.insurers.title"
  | "home.loading"
  | "home.no_channels"
  | "home.title"
  | "home.title_neutral"
  | "inbox.block.citations"
  | "inbox.block.controls"
  | "inbox.block.fields"
  | "inbox.block.rule"
  | "inbox.block.rule_closed"
  | "inbox.block.trace"
  | "inbox.block.transcript"
  | "inbox.case.back"
  | "inbox.case.category"
  | "inbox.case.completeness"
  | "inbox.case.no_category"
  | "inbox.case.no_reason"
  | "inbox.case.not_found"
  | "inbox.case.not_handed_off"
  | "inbox.case.reason"
  | "inbox.case.resolution"
  | "inbox.case.title"
  | "inbox.closed_by_rules.intro"
  | "inbox.closed_by_rules.note"
  | "inbox.completeness"
  | "inbox.controls.all_clear"
  | "inbox.controls.finding.attachment_missing"
  | "inbox.controls.finding.disclosure_missing"
  | "inbox.controls.finding.human_route_missed"
  | "inbox.controls.finding.other"
  | "inbox.controls.reviewed"
  | "inbox.controls.some_findings"
  | "inbox.correction.cancel"
  | "inbox.correction.closed"
  | "inbox.correction.edit"
  | "inbox.correction.save"
  | "inbox.correction.saved"
  | "inbox.correction.value_label"
  | "inbox.coverage.empty"
  | "inbox.coverage.issuer"
  | "inbox.coverage.no_clause_found"
  | "inbox.coverage.question"
  | "inbox.coverage.rejected"
  | "inbox.coverage.unverifiable"
  | "inbox.coverage.verified"
  | "inbox.decision.approve"
  | "inbox.decision.comment_hint"
  | "inbox.decision.comment_label"
  | "inbox.decision.mark_sent"
  | "inbox.decision.none_awaiting"
  | "inbox.decision.none_closed"
  | "inbox.decision.none_closed_by_rules"
  | "inbox.decision.none_in_conversation"
  | "inbox.decision.recorded"
  | "inbox.decision.reject"
  | "inbox.decision.takeover_note"
  | "inbox.decision.title"
  | "inbox.explanation.by_adjuster"
  | "inbox.explanation.by_adjuster_ai"
  | "inbox.explanation.by_adjuster_ai_agency"
  | "inbox.explanation.by_agency"
  | "inbox.explanation.by_rules"
  | "inbox.explanation.by_staff"
  | "inbox.explanation.by_visitor"
  | "inbox.explanation.nobody"
  | "inbox.explanation.pending"
  | "inbox.explanation.title"
  | "inbox.fields.awaiting"
  | "inbox.fields.complete"
  | "inbox.fields.incomplete"
  | "inbox.fields.optional"
  | "inbox.priority.high"
  | "inbox.priority.normal"
  | "inbox.queue.column_case"
  | "inbox.queue.column_category"
  | "inbox.queue.column_channel"
  | "inbox.queue.column_completeness"
  | "inbox.queue.column_language"
  | "inbox.queue.column_priority"
  | "inbox.queue.column_waiting"
  | "inbox.queue.empty"
  | "inbox.queue.empty_filtered"
  | "inbox.queue.filter_any"
  | "inbox.queue.filter_channel"
  | "inbox.queue.filter_clear"
  | "inbox.queue.filter_language"
  | "inbox.queue.filter_priority"
  | "inbox.queue.filter_state"
  | "inbox.queue.filters_label"
  | "inbox.queue.more"
  | "inbox.queue.open"
  | "inbox.queue.results"
  | "inbox.queue.table_label"
  | "inbox.queue.title"
  | "inbox.rule.category.direct_close"
  | "inbox.rule.category.other"
  | "inbox.rule.category.referral"
  | "inbox.rule.category.standard_review"
  | "inbox.rule.reason.direct_close"
  | "inbox.rule.reason.other"
  | "inbox.rule.reason.referral"
  | "inbox.rule.reason.standard_review"
  | "inbox.rule.reference"
  | "inbox.staff_note"
  | "inbox.trace.cost"
  | "inbox.transcript.empty"
  | "inbox.transcript.redacted_hint"
  | "inbox.transcript.speaker_agent"
  | "inbox.transcript.speaker_insured"
  | "inbox.triage.amount_invalid"
  | "inbox.triage.amount_label"
  | "inbox.triage.amount_preview"
  | "inbox.triage.answer_no"
  | "inbox.triage.answer_yes"
  | "inbox.triage.coverage_label"
  | "inbox.triage.fraud_label"
  | "inbox.triage.intro"
  | "inbox.triage.read_only"
  | "inbox.triage.save"
  | "inbox.triage.saved"
  | "inbox.triage.title"
  | "inbox.triage.unset"
  | "inbox.waited.days"
  | "inbox.waited.hours"
  | "inbox.waited.just_now"
  | "inbox.waited.minutes"
  | "insurer.agent.name"
  | "insurer.character.agency"
  | "insurer.character.conservative"
  | "insurer.character.flexible"
  | "intake.degraded"
  | "intake.tone.calm"
  | "intake.tone.closing_abuse"
  | "metrics.cause.criterion_absent"
  | "metrics.cause.criterion_not_built"
  | "metrics.cause.latency_not_in_baseline"
  | "metrics.cause.measured_per_milestone"
  | "metrics.cause.no_baseline"
  | "metrics.cause.not_connected"
  | "metrics.cause.too_few_turns"
  | "metrics.figure.cases_by_tenant"
  | "metrics.figure.citation_precision"
  | "metrics.figure.completeness"
  | "metrics.figure.cost_per_case"
  | "metrics.figure.latency"
  | "metrics.figure_help.cases_by_tenant"
  | "metrics.figure_help.citation_precision"
  | "metrics.figure_help.completeness"
  | "metrics.figure_help.cost_per_case"
  | "metrics.figure_help.latency"
  | "metrics.language.en"
  | "metrics.language.es"
  | "metrics.latency.between"
  | "metrics.latency.chat"
  | "metrics.latency.dataset"
  | "metrics.latency.environment_chat"
  | "metrics.latency.event.first_audio"
  | "metrics.latency.event.first_word"
  | "metrics.latency.event.message_sent"
  | "metrics.latency.event.speech_end"
  | "metrics.latency.half"
  | "metrics.latency.most"
  | "metrics.latency.percentiles"
  | "metrics.latency.turns"
  | "metrics.latency.voice"
  | "metrics.lead"
  | "metrics.loading"
  | "metrics.no_baseline"
  | "metrics.not_measured"
  | "metrics.source.commit"
  | "metrics.source.date"
  | "metrics.source.run"
  | "metrics.title"
  | "policies.ask_chat"
  | "policies.ask_identity"
  | "policies.ask_question"
  | "policies.coverage_title"
  | "policies.endorsement.a_excl_a_5"
  | "policies.endorsement.b_ins"
  | "policies.endorsement.c_arbitration"
  | "policies.endorsement.d_excl_3"
  | "policies.endorsement.d_excl_5"
  | "policies.endorsement.d_transport"
  | "policies.endorsement.def_covered_auto"
  | "policies.endorsement.def_family_member"
  | "policies.endorsement.f_period_territory"
  | "policies.endorsement.f_termination"
  | "policies.endorsements_title"
  | "policies.example"
  | "policies.holder"
  | "policies.intro"
  | "policies.issued_by"
  | "policies.limit.a_bodily_injury_per_accident"
  | "policies.limit.a_bodily_injury_per_person"
  | "policies.limit.a_property_damage"
  | "policies.limit.b_medical_payments_per_person"
  | "policies.limit.c_driver_personal_accident"
  | "policies.limit.d_damage_deductible"
  | "policies.limit.d_theft_deductible"
  | "policies.loading"
  | "policies.money_note"
  | "policies.nav_insurers"
  | "policies.no_endorsements"
  | "policies.period"
  | "policies.question.abroad"
  | "policies.question.covered_auto_definition_changed"
  | "policies.question.hail"
  | "policies.question.lend_car"
  | "policies.question.other_driver_no_insurance"
  | "policies.question.passengers_medical"
  | "policies.question.rental_car"
  | "policies.question.report_deadline"
  | "policies.question.ride_app_exclusion_reopened"
  | "policies.question.temporary_substitute_definition"
  | "policies.question.theft"
  | "policies.question.tire_exclusion_reopened"
  | "policies.question.towing"
  | "policies.question.transport_expense_extension"
  | "policies.questions_hint"
  | "policies.questions_title"
  | "policies.title"
  | "policies.vehicles"
  | "policy_rag.coverage.no_clause_found"
  | "policy_rag.coverage.unverifiable"
  | "problem.conflict"
  | "problem.conflict_state"
  | "problem.forbidden_origin"
  | "problem.link_invalid"
  | "problem.not_found"
  | "problem.service_unavailable"
  | "problem.unverifiable"
  | "problem.validation_failed"
  | "quality.cause.extraction"
  | "quality.cause.infrastructure"
  | "quality.cause.latency"
  | "quality.cause.not_built"
  | "quality.cause.provider_error"
  | "quality.cause.retrieval"
  | "quality.cause.rules"
  | "quality.cause.style"
  | "quality.cause.unknown"
  | "quality.cause.verification"
  | "quality.count.failed"
  | "quality.count.not_measured"
  | "quality.dataset.ds2.help"
  | "quality.dataset.ds2.name"
  | "quality.dataset.ds3.help"
  | "quality.dataset.ds3.name"
  | "quality.dataset.ds4.help"
  | "quality.dataset.ds4.name"
  | "quality.dataset.ds6.help"
  | "quality.dataset.ds6.name"
  | "quality.dataset.ds8.help"
  | "quality.dataset.ds8.name"
  | "quality.dataset.other.help"
  | "quality.dataset.other.name"
  | "quality.datasets.title"
  | "quality.empty"
  | "quality.failures.blocking"
  | "quality.failures.cause"
  | "quality.failures.none"
  | "quality.failures.reference"
  | "quality.failures.title"
  | "quality.gate.all_passed"
  | "quality.gate.citations"
  | "quality.gate.conduct"
  | "quality.gate.content"
  | "quality.gate.isolation"
  | "quality.gate.no_promises"
  | "quality.gate.not_measured"
  | "quality.gate.personal_data"
  | "quality.gate.some_failed"
  | "quality.gates.lead"
  | "quality.gates.title"
  | "quality.intro"
  | "quality.lang.en"
  | "quality.lang.es"
  | "quality.legend.failed"
  | "quality.legend.not_measured"
  | "quality.legend.passed"
  | "quality.loading"
  | "quality.pending.always.chat"
  | "quality.pending.always.voice"
  | "quality.pending.budget_exhausted"
  | "quality.pending.count"
  | "quality.pending.lead"
  | "quality.pending.none"
  | "quality.pending.other"
  | "quality.pending.provider_key_missing"
  | "quality.pending.provider_timeout"
  | "quality.pending.provider_unavailable"
  | "quality.pending.quota_exhausted"
  | "quality.pending.runner_timeout"
  | "quality.pending.target_unavailable"
  | "quality.pending.title"
  | "quality.run.commit"
  | "quality.run.details"
  | "quality.run.dirty"
  | "quality.run.duration"
  | "quality.run.models"
  | "quality.run.not_comparable"
  | "quality.run.when"
  | "quality.totals.hint"
  | "quality.totals.passed"
  | "shell.brand_name"
  | "shell.footer.demo"
  | "shell.footer.github"
  | "shell.footer.github_label"
  | "shell.footer.linkedin"
  | "shell.footer.linkedin_label"
  | "shell.footer.made_by"
  | "shell.language.changed"
  | "shell.language.en"
  | "shell.language.es"
  | "shell.language.group"
  | "shell.loading"
  | "shell.menu.button"
  | "shell.nav.landing"
  | "shell.nav_label"
  | "shell.skip_to_content"
  | "shell.theme.dark"
  | "shell.theme.group"
  | "shell.theme.light"
  | "site.link.readme"
  | "site.link.video"
  | "spend.quota.budget_exhausted"
  | "spend.quota.rate_limited_daily"
  | "spend.quota.rate_limited_session"
  | "spend.quota.rate_limited_site"
  | "spend_panel.activity.calls"
  | "spend_panel.activity.calls_help"
  | "spend_panel.activity.chat"
  | "spend_panel.activity.chat_help"
  | "spend_panel.activity.lead"
  | "spend_panel.activity.operations"
  | "spend_panel.activity.operations_help"
  | "spend_panel.activity.policy_reading"
  | "spend_panel.activity.policy_reading_help"
  | "spend_panel.activity.quality_tests"
  | "spend_panel.activity.quality_tests_help"
  | "spend_panel.activity.share"
  | "spend_panel.activity.title"
  | "spend_panel.cases.channel_chat"
  | "spend_panel.cases.channel_voice"
  | "spend_panel.cases.comparison_hint"
  | "spend_panel.cases.describe"
  | "spend_panel.cases.describe_comparison"
  | "spend_panel.cases.describe_comparison_one"
  | "spend_panel.cases.empty"
  | "spend_panel.cases.label"
  | "spend_panel.cases.lead"
  | "spend_panel.cases.mine"
  | "spend_panel.cases.title"
  | "spend_panel.cases.type_claim"
  | "spend_panel.cases.type_coverage_inquiry"
  | "spend_panel.cases.type_quote_request"
  | "spend_panel.cases.yours"
  | "spend_panel.daily.bar"
  | "spend_panel.daily.lead"
  | "spend_panel.daily.quiet"
  | "spend_panel.daily.title"
  | "spend_panel.kpi.budget"
  | "spend_panel.kpi.budget_hint"
  | "spend_panel.kpi.none_hint"
  | "spend_panel.kpi.none_yet"
  | "spend_panel.kpi.per_call"
  | "spend_panel.kpi.per_call_hint"
  | "spend_panel.kpi.per_chat"
  | "spend_panel.kpi.per_chat_hint"
  | "spend_panel.kpi.total"
  | "spend_panel.kpi.total_hint"
  | "spend_panel.loading"
  | "spend_panel.not_measured"
  | "spend_panel.provider.anthropic"
  | "spend_panel.provider.anthropic_role"
  | "spend_panel.provider.cartesia"
  | "spend_panel.provider.cartesia_role"
  | "spend_panel.provider.deepgram"
  | "spend_panel.provider.deepgram_role"
  | "spend_panel.provider.gemini"
  | "spend_panel.provider.gemini_role"
  | "spend_panel.provider.lead"
  | "spend_panel.provider.models"
  | "spend_panel.provider.title"
  | "spend_panel.status_value.alerted"
  | "spend_panel.status_value.exhausted"
  | "spend_panel.status_value.ok"
  | "spend_panel.status_value.unmeasured"
  | "spend_panel.tokens.also"
  | "spend_panel.tokens.also_lookups"
  | "spend_panel.tokens.count"
  | "spend_panel.tokens.free_plan"
  | "spend_panel.tokens.lookup_one"
  | "spend_panel.tokens.lookups"
  | "spend_panel.window.alert_label"
  | "spend_panel.window.cap_label"
  | "spend_panel.window.lead"
  | "spend_panel.window.none"
  | "spend_panel.window.range"
  | "spend_panel.window.remaining"
  | "spend_panel.window.title"
  | "status.data_reset.body"
  | "status.data_reset.title"
  | "status.link_expired.body"
  | "status.link_expired.title"
  | "status.link_invalid.body"
  | "status.link_invalid.title"
  | "status.not_found.body"
  | "status.not_found.title"
  | "status.service_unavailable.body"
  | "status.service_unavailable.title"
  | "status.unavailable.body"
  | "status.unavailable.title"
  | "surface.comparison"
  | "surface.telemetry"
  | "telemetry.lead"
  | "telemetry.tab_cost"
  | "telemetry.tab_quality"
  | "telemetry.title"
  | "trace.node.compliance"
  | "trace.node.decision"
  | "trace.node.intake"
  | "trace.node.policy_verification"
  | "trace.page.back"
  | "trace.page.clauses"
  | "trace.page.cost"
  | "trace.page.latency"
  | "trace.page.milliseconds"
  | "trace.page.nodes"
  | "trace.page.not_measured"
  | "trace.page.nothing_here"
  | "trace.page.recording_hint"
  | "trace.page.title"
  | "trace.summary.lost"
  | "trace.summary.ready"
  | "trace.summary.recording"
  | "visitor.block.fields"
  | "visitor.intro"
  | "visitor.number"
  | "visitor.opening"
  | "visitor.status.title"
  | "visitor.title_claim"
  | "visitor.title_inquiry"
  | "visitor.title_quote"
  | "visitor.valid_until"
  | "voice.availability.misconfigured"
  | "voice.availability.not_configured"
  | "voice.availability.rate_limited_daily"
  | "voice.availability.rate_limited_site"
  | "voice.console.audio_blocked"
  | "voice.console.audio_enable"
  | "voice.console.call"
  | "voice.console.call_language"
  | "voice.console.checking"
  | "voice.console.connecting"
  | "voice.console.fallback_voice"
  | "voice.console.hangup"
  | "voice.console.interrupted"
  | "voice.console.intro"
  | "voice.console.last_latency"
  | "voice.console.limit_daily"
  | "voice.console.limit_minutes"
  | "voice.console.limit_seconds"
  | "voice.console.mic_denied"
  | "voice.console.mic_help"
  | "voice.console.no_audio"
  | "voice.console.outcome_awaiting"
  | "voice.console.outcome_chat"
  | "voice.console.outcome_closed"
  | "voice.console.outcome_derived"
  | "voice.console.outcome_hand_off"
  | "voice.console.outcome_in_progress"
  | "voice.console.outcome_number"
  | "voice.console.outcome_open_case"
  | "voice.console.outcome_title"
  | "voice.console.sample_button"
  | "voice.console.sample_intro"
  | "voice.console.sample_say"
  | "voice.console.sample_say_number"
  | "voice.console.speaker_insured"
  | "voice.console.time_left"
  | "voice.console.time_left_label"
  | "voice.console.title"
  | "voice.console.transcript_label"
  | "voice.console.unavailable"
  | "voice.console.use_chat"
  | "voice.ended.completed"
  | "voice.ended.dropped"
  | "voice.ended.error"
  | "voice.ended.handed_off"
  | "voice.ended.max_duration"
  | "voice.ended.resume_until"
  | "voice.ended.saved"
  | "voice.ended.silence"
  | "voice.mic_check.answer_no"
  | "voice.mic_check.answer_yes"
  | "voice.mic_check.browser_default"
  | "voice.mic_check.choose"
  | "voice.mic_check.detail"
  | "voice.mic_check.device"
  | "voice.mic_check.failed"
  | "voice.mic_check.listening"
  | "voice.mic_check.ok"
  | "voice.mic_check.silent"
  | "voice.mic_check.start"
  | "voice.notice.time_running_out"
  | "voice.state.ended"
  | "voice.state.listening"
  | "voice.state.speaking";

/** Los idiomas admitidos por el producto. */
export type Locale = "es" | "en";

/** Donde se muestra una frase. */
export type Surface = "chat" | "inbox" | "system" | "voice";

/** Las claves, para recorrerlas en tiempo de ejecucion. */
export const COPY_KEYS = [
  "action.back_to_conversation",
  "action.go_home",
  "action.retry",
  "action.start_over",
  "adjuster.panel.ai_notice",
  "adjuster.panel.capped",
  "adjuster.panel.decided",
  "adjuster.panel.decision",
  "adjuster.panel.failed",
  "adjuster.panel.running",
  "adjuster.panel.sources",
  "adjuster.panel.steps",
  "adjuster.panel.title",
  "adjuster.panel.title_pending",
  "adjuster.source.kind.clause",
  "adjuster.source.kind.web",
  "adjuster.source.new_tab",
  "adjuster.source.rule",
  "adjuster.step.case_read.title",
  "adjuster.step.clauses.title",
  "adjuster.step.decision.title",
  "adjuster.step.policy_read.title",
  "adjuster.step.rules.title",
  "adjuster.step.vehicle_value.title",
  "case.channel.chat",
  "case.channel.voice",
  "case.derivation_reason.demo_limit",
  "case.derivation_reason.person_requested",
  "case.derivation_reason.rule",
  "case.field.annual_mileage_band",
  "case.field.at_fault_losses_3y",
  "case.field.claims_3y",
  "case.field.description",
  "case.field.driver_birth_date",
  "case.field.driver_name",
  "case.field.garaging_jurisdiction",
  "case.field.identity_and_policy",
  "case.field.incident_datetime",
  "case.field.injuries",
  "case.field.lapse_months",
  "case.field.license_jurisdiction",
  "case.field.license_years",
  "case.field.location",
  "case.field.other_parties",
  "case.field.prior_coverage_active",
  "case.field.question_asked",
  "case.field.salvage_title",
  "case.field.use_type",
  "case.field.vehicle_age_years",
  "case.field.vehicle_and_driver",
  "case.field.vehicle_make",
  "case.field.vehicle_model",
  "case.field.vehicle_year",
  "case.field.vin",
  "case.field_unavailable",
  "case.record_type.claim",
  "case.record_type.coverage_inquiry",
  "case.record_type.quote_request",
  "case.resolution.approved",
  "case.resolution.registered",
  "case.resolution.rejected",
  "case.resolution.sent_to_insurer",
  "case.state.awaiting_insured",
  "case.state.capturing",
  "case.state.closed",
  "case.state.deciding",
  "case.state.derived",
  "case.state.open",
  "case.state.verifying",
  "cases.example.back",
  "cases.example.note",
  "cases.example.title",
  "cases.examples.empty",
  "cases.examples.hint",
  "cases.examples.insurer_label",
  "cases.examples.title",
  "cases.group.awaiting_insured",
  "cases.group.capturing",
  "cases.group.closed",
  "cases.group.deciding",
  "cases.group.derived",
  "cases.group.verifying",
  "cases.intro",
  "cases.mine.chat",
  "cases.mine.chat_with",
  "cases.mine.empty",
  "cases.mine.hint",
  "cases.mine.number",
  "cases.mine.title",
  "cases.mine.view",
  "cases.mine.view_of",
  "cases.nav",
  "cases.start",
  "cases.title",
  "chat.chip.add_more",
  "chat.chip.adjuster_review",
  "chat.chip.another_question",
  "chat.chip.answer_no",
  "chat.chip.answer_yes",
  "chat.chip.example_holder",
  "chat.chip.example_policy",
  "chat.chip.leave_it",
  "chat.chip.mileage_high",
  "chat.chip.mileage_low",
  "chat.chip.mileage_medium",
  "chat.chip.nobody_hurt",
  "chat.chip.policy_question",
  "chat.chip.quote",
  "chat.chip.report",
  "chat.chip.someone_hurt",
  "chat.chip.today",
  "chat.chip.use_commercial",
  "chat.chip.use_commuting",
  "chat.chip.use_personal",
  "chat.chip.yesterday",
  "chat.citation.amount_deferred",
  "chat.citation.expand",
  "chat.citation.hide_original",
  "chat.citation.language_en",
  "chat.citation.language_es",
  "chat.citation.other_language",
  "chat.citation.position",
  "chat.citation.reference",
  "chat.citation.show_original",
  "chat.citation.special_condition",
  "chat.citation.trace_link",
  "chat.citation.translation_note",
  "chat.greeting.hello",
  "chat.limit.rate",
  "chat.limit.site_day",
  "chat.limit.size",
  "chat.opening.capabilities",
  "chat.opening.capabilities_with_quote",
  "chat.opening.disclosure",
  "chat.page.answering_in",
  "chat.page.case_complete",
  "chat.page.case_kind_claim",
  "chat.page.case_kind_inquiry",
  "chat.page.case_kind_other",
  "chat.page.case_kind_quote",
  "chat.page.case_link",
  "chat.page.case_missing_many",
  "chat.page.case_missing_one",
  "chat.page.case_number",
  "chat.page.composer_hint",
  "chat.page.composer_label",
  "chat.page.connecting",
  "chat.page.history_restored",
  "chat.page.reset",
  "chat.page.reset_body",
  "chat.page.reset_body_with_case",
  "chat.page.reset_cancel",
  "chat.page.reset_confirm",
  "chat.page.reset_title",
  "chat.page.reviewing",
  "chat.page.see_reasoning",
  "chat.page.send",
  "chat.page.speaker_visitor",
  "chat.page.speaking_in",
  "chat.page.title",
  "chat.page.transcript_label",
  "chat.page.typing",
  "chat.reasoning.adjuster_decides",
  "chat.reasoning.clause_not_verified",
  "chat.reasoning.clause_verified",
  "chat.reasoning.empty",
  "chat.reasoning.missing",
  "chat.reasoning.noted",
  "chat.reasoning.optional",
  "chat.reasoning.outcome_no_clause",
  "chat.reasoning.outcome_rejected",
  "chat.reasoning.outcome_unverifiable",
  "chat.reasoning.outcome_verified",
  "chat.reasoning.policy_confirmed",
  "chat.reasoning.policy_missing",
  "chat.reasoning.state_closed",
  "chat.reasoning.state_derived",
  "chat.reasoning.state_open",
  "chat.reasoning.step_checked",
  "chat.reasoning.step_next",
  "chat.reasoning.step_noted",
  "chat.reasoning.step_policy",
  "chat.reasoning.step_understood",
  "chat.reasoning.title",
  "chat.reasoning.wants_claim",
  "chat.reasoning.wants_question",
  "chat.reasoning.wants_quote",
  "chat.reasoning.you_asked",
  "chat.turn.error",
  "chat.turn.waiting",
  "comparison.asked.label",
  "comparison.asked.meta",
  "comparison.asked.new",
  "comparison.column.failed",
  "comparison.column.idle",
  "comparison.column.interrupted",
  "comparison.column.loading",
  "comparison.column.policy",
  "comparison.column.policy_issued_by",
  "comparison.column.rejected_title",
  "comparison.column.retry",
  "comparison.composer.label",
  "comparison.composer.send",
  "comparison.disclosure.assistant",
  "comparison.disclosure.demo",
  "comparison.disclosure.incomplete",
  "comparison.examples.blown_tire",
  "comparison.examples.hail",
  "comparison.examples.lend_car",
  "comparison.examples.other_driver_no_insurance",
  "comparison.examples.passenger_medical",
  "comparison.examples.rental_car",
  "comparison.examples.ride_app",
  "comparison.examples.stolen_keys",
  "comparison.examples.title",
  "comparison.out_of_scope.chat_link",
  "comparison.out_of_scope.explanation",
  "comparison.page.lead",
  "comparison.page.loading",
  "comparison.page.title",
  "comparison.state.answered",
  "comparison.state.failed",
  "comparison.state.interrupted",
  "comparison.state.loading",
  "comparison.state.rejected",
  "compliance.closure.direct",
  "compliance.emergency.local",
  "compliance.emergency.public",
  "compliance.guard.amount",
  "compliance.guard.config_disclosure",
  "compliance.guard.coverage_promise",
  "compliance.guard.degraded",
  "compliance.guard.fault",
  "compliance.guard.legal_advice",
  "compliance.guard.transfer_or_deadline",
  "compliance.handoff.adjuster_review",
  "compliance.handoff.adjuster_review_inquiry",
  "demo.notice.label",
  "demo.notice.less",
  "demo.notice.more",
  "demo.reset.conversation_notice",
  "demo.reset.surfaces_closed",
  "documents.amended_by",
  "documents.cited",
  "documents.clause_count",
  "documents.close",
  "documents.how",
  "documents.kind_base",
  "documents.kind_endorsement",
  "documents.kind_jurisdiction",
  "documents.list_label",
  "documents.loading",
  "documents.no_match",
  "documents.not_in_force",
  "documents.not_in_force_why",
  "documents.open",
  "documents.search_label",
  "documents.show_original",
  "documents.show_translation",
  "documents.static",
  "documents.title",
  "documents.translation_note",
  "evals.scripted_insured.unknown_field",
  "guide.about.limit",
  "guide.about.sample",
  "guide.about.what",
  "guide.differences.agent",
  "guide.differences.same",
  "guide.differences.tip",
  "guide.differences.title",
  "guide.start",
  "guide.steps.adjuster.body",
  "guide.steps.adjuster.title",
  "guide.steps.choose.body",
  "guide.steps.choose.title",
  "guide.steps.link.body",
  "guide.steps.link.title",
  "guide.steps.report.both",
  "guide.steps.report.chat",
  "guide.steps.report.policy",
  "guide.steps.report.title",
  "guide.steps.report.voice",
  "guide.steps.title",
  "guide.title",
  "guide.try.ask_coverage",
  "guide.try.cases",
  "guide.try.compare",
  "guide.try.interrupt",
  "guide.try.telemetry",
  "guide.try.title",
  "home.action.chat",
  "home.action.chat_with",
  "home.action.policies",
  "home.action.policies_of",
  "home.action.voice",
  "home.action.voice_with",
  "home.demo_line",
  "home.how.report_both",
  "home.how.report_chat",
  "home.how.report_voice",
  "home.how.title",
  "home.insurers.title",
  "home.loading",
  "home.no_channels",
  "home.title",
  "home.title_neutral",
  "inbox.block.citations",
  "inbox.block.controls",
  "inbox.block.fields",
  "inbox.block.rule",
  "inbox.block.rule_closed",
  "inbox.block.trace",
  "inbox.block.transcript",
  "inbox.case.back",
  "inbox.case.category",
  "inbox.case.completeness",
  "inbox.case.no_category",
  "inbox.case.no_reason",
  "inbox.case.not_found",
  "inbox.case.not_handed_off",
  "inbox.case.reason",
  "inbox.case.resolution",
  "inbox.case.title",
  "inbox.closed_by_rules.intro",
  "inbox.closed_by_rules.note",
  "inbox.completeness",
  "inbox.controls.all_clear",
  "inbox.controls.finding.attachment_missing",
  "inbox.controls.finding.disclosure_missing",
  "inbox.controls.finding.human_route_missed",
  "inbox.controls.finding.other",
  "inbox.controls.reviewed",
  "inbox.controls.some_findings",
  "inbox.correction.cancel",
  "inbox.correction.closed",
  "inbox.correction.edit",
  "inbox.correction.save",
  "inbox.correction.saved",
  "inbox.correction.value_label",
  "inbox.coverage.empty",
  "inbox.coverage.issuer",
  "inbox.coverage.no_clause_found",
  "inbox.coverage.question",
  "inbox.coverage.rejected",
  "inbox.coverage.unverifiable",
  "inbox.coverage.verified",
  "inbox.decision.approve",
  "inbox.decision.comment_hint",
  "inbox.decision.comment_label",
  "inbox.decision.mark_sent",
  "inbox.decision.none_awaiting",
  "inbox.decision.none_closed",
  "inbox.decision.none_closed_by_rules",
  "inbox.decision.none_in_conversation",
  "inbox.decision.recorded",
  "inbox.decision.reject",
  "inbox.decision.takeover_note",
  "inbox.decision.title",
  "inbox.explanation.by_adjuster",
  "inbox.explanation.by_adjuster_ai",
  "inbox.explanation.by_adjuster_ai_agency",
  "inbox.explanation.by_agency",
  "inbox.explanation.by_rules",
  "inbox.explanation.by_staff",
  "inbox.explanation.by_visitor",
  "inbox.explanation.nobody",
  "inbox.explanation.pending",
  "inbox.explanation.title",
  "inbox.fields.awaiting",
  "inbox.fields.complete",
  "inbox.fields.incomplete",
  "inbox.fields.optional",
  "inbox.priority.high",
  "inbox.priority.normal",
  "inbox.queue.column_case",
  "inbox.queue.column_category",
  "inbox.queue.column_channel",
  "inbox.queue.column_completeness",
  "inbox.queue.column_language",
  "inbox.queue.column_priority",
  "inbox.queue.column_waiting",
  "inbox.queue.empty",
  "inbox.queue.empty_filtered",
  "inbox.queue.filter_any",
  "inbox.queue.filter_channel",
  "inbox.queue.filter_clear",
  "inbox.queue.filter_language",
  "inbox.queue.filter_priority",
  "inbox.queue.filter_state",
  "inbox.queue.filters_label",
  "inbox.queue.more",
  "inbox.queue.open",
  "inbox.queue.results",
  "inbox.queue.table_label",
  "inbox.queue.title",
  "inbox.rule.category.direct_close",
  "inbox.rule.category.other",
  "inbox.rule.category.referral",
  "inbox.rule.category.standard_review",
  "inbox.rule.reason.direct_close",
  "inbox.rule.reason.other",
  "inbox.rule.reason.referral",
  "inbox.rule.reason.standard_review",
  "inbox.rule.reference",
  "inbox.staff_note",
  "inbox.trace.cost",
  "inbox.transcript.empty",
  "inbox.transcript.redacted_hint",
  "inbox.transcript.speaker_agent",
  "inbox.transcript.speaker_insured",
  "inbox.triage.amount_invalid",
  "inbox.triage.amount_label",
  "inbox.triage.amount_preview",
  "inbox.triage.answer_no",
  "inbox.triage.answer_yes",
  "inbox.triage.coverage_label",
  "inbox.triage.fraud_label",
  "inbox.triage.intro",
  "inbox.triage.read_only",
  "inbox.triage.save",
  "inbox.triage.saved",
  "inbox.triage.title",
  "inbox.triage.unset",
  "inbox.waited.days",
  "inbox.waited.hours",
  "inbox.waited.just_now",
  "inbox.waited.minutes",
  "insurer.agent.name",
  "insurer.character.agency",
  "insurer.character.conservative",
  "insurer.character.flexible",
  "intake.degraded",
  "intake.tone.calm",
  "intake.tone.closing_abuse",
  "metrics.cause.criterion_absent",
  "metrics.cause.criterion_not_built",
  "metrics.cause.latency_not_in_baseline",
  "metrics.cause.measured_per_milestone",
  "metrics.cause.no_baseline",
  "metrics.cause.not_connected",
  "metrics.cause.too_few_turns",
  "metrics.figure.cases_by_tenant",
  "metrics.figure.citation_precision",
  "metrics.figure.completeness",
  "metrics.figure.cost_per_case",
  "metrics.figure.latency",
  "metrics.figure_help.cases_by_tenant",
  "metrics.figure_help.citation_precision",
  "metrics.figure_help.completeness",
  "metrics.figure_help.cost_per_case",
  "metrics.figure_help.latency",
  "metrics.language.en",
  "metrics.language.es",
  "metrics.latency.between",
  "metrics.latency.chat",
  "metrics.latency.dataset",
  "metrics.latency.environment_chat",
  "metrics.latency.event.first_audio",
  "metrics.latency.event.first_word",
  "metrics.latency.event.message_sent",
  "metrics.latency.event.speech_end",
  "metrics.latency.half",
  "metrics.latency.most",
  "metrics.latency.percentiles",
  "metrics.latency.turns",
  "metrics.latency.voice",
  "metrics.lead",
  "metrics.loading",
  "metrics.no_baseline",
  "metrics.not_measured",
  "metrics.source.commit",
  "metrics.source.date",
  "metrics.source.run",
  "metrics.title",
  "policies.ask_chat",
  "policies.ask_identity",
  "policies.ask_question",
  "policies.coverage_title",
  "policies.endorsement.a_excl_a_5",
  "policies.endorsement.b_ins",
  "policies.endorsement.c_arbitration",
  "policies.endorsement.d_excl_3",
  "policies.endorsement.d_excl_5",
  "policies.endorsement.d_transport",
  "policies.endorsement.def_covered_auto",
  "policies.endorsement.def_family_member",
  "policies.endorsement.f_period_territory",
  "policies.endorsement.f_termination",
  "policies.endorsements_title",
  "policies.example",
  "policies.holder",
  "policies.intro",
  "policies.issued_by",
  "policies.limit.a_bodily_injury_per_accident",
  "policies.limit.a_bodily_injury_per_person",
  "policies.limit.a_property_damage",
  "policies.limit.b_medical_payments_per_person",
  "policies.limit.c_driver_personal_accident",
  "policies.limit.d_damage_deductible",
  "policies.limit.d_theft_deductible",
  "policies.loading",
  "policies.money_note",
  "policies.nav_insurers",
  "policies.no_endorsements",
  "policies.period",
  "policies.question.abroad",
  "policies.question.covered_auto_definition_changed",
  "policies.question.hail",
  "policies.question.lend_car",
  "policies.question.other_driver_no_insurance",
  "policies.question.passengers_medical",
  "policies.question.rental_car",
  "policies.question.report_deadline",
  "policies.question.ride_app_exclusion_reopened",
  "policies.question.temporary_substitute_definition",
  "policies.question.theft",
  "policies.question.tire_exclusion_reopened",
  "policies.question.towing",
  "policies.question.transport_expense_extension",
  "policies.questions_hint",
  "policies.questions_title",
  "policies.title",
  "policies.vehicles",
  "policy_rag.coverage.no_clause_found",
  "policy_rag.coverage.unverifiable",
  "problem.conflict",
  "problem.conflict_state",
  "problem.forbidden_origin",
  "problem.link_invalid",
  "problem.not_found",
  "problem.service_unavailable",
  "problem.unverifiable",
  "problem.validation_failed",
  "quality.cause.extraction",
  "quality.cause.infrastructure",
  "quality.cause.latency",
  "quality.cause.not_built",
  "quality.cause.provider_error",
  "quality.cause.retrieval",
  "quality.cause.rules",
  "quality.cause.style",
  "quality.cause.unknown",
  "quality.cause.verification",
  "quality.count.failed",
  "quality.count.not_measured",
  "quality.dataset.ds2.help",
  "quality.dataset.ds2.name",
  "quality.dataset.ds3.help",
  "quality.dataset.ds3.name",
  "quality.dataset.ds4.help",
  "quality.dataset.ds4.name",
  "quality.dataset.ds6.help",
  "quality.dataset.ds6.name",
  "quality.dataset.ds8.help",
  "quality.dataset.ds8.name",
  "quality.dataset.other.help",
  "quality.dataset.other.name",
  "quality.datasets.title",
  "quality.empty",
  "quality.failures.blocking",
  "quality.failures.cause",
  "quality.failures.none",
  "quality.failures.reference",
  "quality.failures.title",
  "quality.gate.all_passed",
  "quality.gate.citations",
  "quality.gate.conduct",
  "quality.gate.content",
  "quality.gate.isolation",
  "quality.gate.no_promises",
  "quality.gate.not_measured",
  "quality.gate.personal_data",
  "quality.gate.some_failed",
  "quality.gates.lead",
  "quality.gates.title",
  "quality.intro",
  "quality.lang.en",
  "quality.lang.es",
  "quality.legend.failed",
  "quality.legend.not_measured",
  "quality.legend.passed",
  "quality.loading",
  "quality.pending.always.chat",
  "quality.pending.always.voice",
  "quality.pending.budget_exhausted",
  "quality.pending.count",
  "quality.pending.lead",
  "quality.pending.none",
  "quality.pending.other",
  "quality.pending.provider_key_missing",
  "quality.pending.provider_timeout",
  "quality.pending.provider_unavailable",
  "quality.pending.quota_exhausted",
  "quality.pending.runner_timeout",
  "quality.pending.target_unavailable",
  "quality.pending.title",
  "quality.run.commit",
  "quality.run.details",
  "quality.run.dirty",
  "quality.run.duration",
  "quality.run.models",
  "quality.run.not_comparable",
  "quality.run.when",
  "quality.totals.hint",
  "quality.totals.passed",
  "shell.brand_name",
  "shell.footer.demo",
  "shell.footer.github",
  "shell.footer.github_label",
  "shell.footer.linkedin",
  "shell.footer.linkedin_label",
  "shell.footer.made_by",
  "shell.language.changed",
  "shell.language.en",
  "shell.language.es",
  "shell.language.group",
  "shell.loading",
  "shell.menu.button",
  "shell.nav.landing",
  "shell.nav_label",
  "shell.skip_to_content",
  "shell.theme.dark",
  "shell.theme.group",
  "shell.theme.light",
  "site.link.readme",
  "site.link.video",
  "spend.quota.budget_exhausted",
  "spend.quota.rate_limited_daily",
  "spend.quota.rate_limited_session",
  "spend.quota.rate_limited_site",
  "spend_panel.activity.calls",
  "spend_panel.activity.calls_help",
  "spend_panel.activity.chat",
  "spend_panel.activity.chat_help",
  "spend_panel.activity.lead",
  "spend_panel.activity.operations",
  "spend_panel.activity.operations_help",
  "spend_panel.activity.policy_reading",
  "spend_panel.activity.policy_reading_help",
  "spend_panel.activity.quality_tests",
  "spend_panel.activity.quality_tests_help",
  "spend_panel.activity.share",
  "spend_panel.activity.title",
  "spend_panel.cases.channel_chat",
  "spend_panel.cases.channel_voice",
  "spend_panel.cases.comparison_hint",
  "spend_panel.cases.describe",
  "spend_panel.cases.describe_comparison",
  "spend_panel.cases.describe_comparison_one",
  "spend_panel.cases.empty",
  "spend_panel.cases.label",
  "spend_panel.cases.lead",
  "spend_panel.cases.mine",
  "spend_panel.cases.title",
  "spend_panel.cases.type_claim",
  "spend_panel.cases.type_coverage_inquiry",
  "spend_panel.cases.type_quote_request",
  "spend_panel.cases.yours",
  "spend_panel.daily.bar",
  "spend_panel.daily.lead",
  "spend_panel.daily.quiet",
  "spend_panel.daily.title",
  "spend_panel.kpi.budget",
  "spend_panel.kpi.budget_hint",
  "spend_panel.kpi.none_hint",
  "spend_panel.kpi.none_yet",
  "spend_panel.kpi.per_call",
  "spend_panel.kpi.per_call_hint",
  "spend_panel.kpi.per_chat",
  "spend_panel.kpi.per_chat_hint",
  "spend_panel.kpi.total",
  "spend_panel.kpi.total_hint",
  "spend_panel.loading",
  "spend_panel.not_measured",
  "spend_panel.provider.anthropic",
  "spend_panel.provider.anthropic_role",
  "spend_panel.provider.cartesia",
  "spend_panel.provider.cartesia_role",
  "spend_panel.provider.deepgram",
  "spend_panel.provider.deepgram_role",
  "spend_panel.provider.gemini",
  "spend_panel.provider.gemini_role",
  "spend_panel.provider.lead",
  "spend_panel.provider.models",
  "spend_panel.provider.title",
  "spend_panel.status_value.alerted",
  "spend_panel.status_value.exhausted",
  "spend_panel.status_value.ok",
  "spend_panel.status_value.unmeasured",
  "spend_panel.tokens.also",
  "spend_panel.tokens.also_lookups",
  "spend_panel.tokens.count",
  "spend_panel.tokens.free_plan",
  "spend_panel.tokens.lookup_one",
  "spend_panel.tokens.lookups",
  "spend_panel.window.alert_label",
  "spend_panel.window.cap_label",
  "spend_panel.window.lead",
  "spend_panel.window.none",
  "spend_panel.window.range",
  "spend_panel.window.remaining",
  "spend_panel.window.title",
  "status.data_reset.body",
  "status.data_reset.title",
  "status.link_expired.body",
  "status.link_expired.title",
  "status.link_invalid.body",
  "status.link_invalid.title",
  "status.not_found.body",
  "status.not_found.title",
  "status.service_unavailable.body",
  "status.service_unavailable.title",
  "status.unavailable.body",
  "status.unavailable.title",
  "surface.comparison",
  "surface.telemetry",
  "telemetry.lead",
  "telemetry.tab_cost",
  "telemetry.tab_quality",
  "telemetry.title",
  "trace.node.compliance",
  "trace.node.decision",
  "trace.node.intake",
  "trace.node.policy_verification",
  "trace.page.back",
  "trace.page.clauses",
  "trace.page.cost",
  "trace.page.latency",
  "trace.page.milliseconds",
  "trace.page.nodes",
  "trace.page.not_measured",
  "trace.page.nothing_here",
  "trace.page.recording_hint",
  "trace.page.title",
  "trace.summary.lost",
  "trace.summary.ready",
  "trace.summary.recording",
  "visitor.block.fields",
  "visitor.intro",
  "visitor.number",
  "visitor.opening",
  "visitor.status.title",
  "visitor.title_claim",
  "visitor.title_inquiry",
  "visitor.title_quote",
  "visitor.valid_until",
  "voice.availability.misconfigured",
  "voice.availability.not_configured",
  "voice.availability.rate_limited_daily",
  "voice.availability.rate_limited_site",
  "voice.console.audio_blocked",
  "voice.console.audio_enable",
  "voice.console.call",
  "voice.console.call_language",
  "voice.console.checking",
  "voice.console.connecting",
  "voice.console.fallback_voice",
  "voice.console.hangup",
  "voice.console.interrupted",
  "voice.console.intro",
  "voice.console.last_latency",
  "voice.console.limit_daily",
  "voice.console.limit_minutes",
  "voice.console.limit_seconds",
  "voice.console.mic_denied",
  "voice.console.mic_help",
  "voice.console.no_audio",
  "voice.console.outcome_awaiting",
  "voice.console.outcome_chat",
  "voice.console.outcome_closed",
  "voice.console.outcome_derived",
  "voice.console.outcome_hand_off",
  "voice.console.outcome_in_progress",
  "voice.console.outcome_number",
  "voice.console.outcome_open_case",
  "voice.console.outcome_title",
  "voice.console.sample_button",
  "voice.console.sample_intro",
  "voice.console.sample_say",
  "voice.console.sample_say_number",
  "voice.console.speaker_insured",
  "voice.console.time_left",
  "voice.console.time_left_label",
  "voice.console.title",
  "voice.console.transcript_label",
  "voice.console.unavailable",
  "voice.console.use_chat",
  "voice.ended.completed",
  "voice.ended.dropped",
  "voice.ended.error",
  "voice.ended.handed_off",
  "voice.ended.max_duration",
  "voice.ended.resume_until",
  "voice.ended.saved",
  "voice.ended.silence",
  "voice.mic_check.answer_no",
  "voice.mic_check.answer_yes",
  "voice.mic_check.browser_default",
  "voice.mic_check.choose",
  "voice.mic_check.detail",
  "voice.mic_check.device",
  "voice.mic_check.failed",
  "voice.mic_check.listening",
  "voice.mic_check.ok",
  "voice.mic_check.silent",
  "voice.mic_check.start",
  "voice.notice.time_running_out",
  "voice.state.ended",
  "voice.state.listening",
  "voice.state.speaking",
] as const satisfies readonly CopyKey[];

export const LOCALES = ["es", "en"] as const satisfies readonly Locale[];
