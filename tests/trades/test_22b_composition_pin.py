"""Arc 22-B Task 2A -- the 22-A2 composition pin (R0.I, CHARC-ruled (a)).

22-A2's acceptance cases stay GREEN byte-unchanged on 22-B's tree (brief
section 4.8), with EXACTLY THREE named exemptions: A2-18, A2-19 and A2-22 were
HEAD claims wearing 0039's name, re-scoped ONCE to ``target_version=39`` so no
later migration meets them again.

Every implementing test function of the 106 ``CASES_22A2`` ids (found by the
A2-08 discovery rule: a module-level ``test_*`` carrying the ``a2_NN`` token) is
pinned by sha256 of ``inspect.getsource``, captured at base ``e61dad27`` (the
22-B executing branch point, before any 22-B edit). Editing any of them is a
visible red, never a quiet re-baseline.
"""
from __future__ import annotations

import hashlib
import importlib
import inspect
from pathlib import Path

from tests.trades.case_registry_22a2 import CASES_22A2, token
from tests.trades.test_22a2_case_closure import _roster_tokens_in_tests

_M1 = "tests/cli/test_correct_cohort_provenance_command.py"
_M2 = "tests/data/test_22a2_barrier_drop_scan.py"
_M3 = "tests/data/test_backup_gate_table.py"
_M4 = "tests/data/test_migration_0039_provenance_corrections_tier2.py"
_M5 = "tests/trades/test_22a2_acceptance_trade25.py"
_M6 = "tests/trades/test_22a2_case_closure.py"
_M7 = "tests/trades/test_22a2_cohort_readers.py"
_M8 = "tests/trades/test_22a2_conjunction.py"
_M9 = "tests/trades/test_22a2_correction_service.py"
_M10 = "tests/trades/test_22a2_frozen_value_preflight.py"
_M11 = "tests/trades/test_22a2_replay.py"
_M12 = "tests/trades/test_22a2_rung9_escape.py"

# (module, function) -> sha256(inspect.getsource(fn)) at base e61dad27.
BASE_PINS_22A2: dict[tuple[str, str], str] = {
    (_M2,
     "test_a2_01_drop_barrier_trigger_is_violation"):
        "62855750784429f3498d1b3e5904fe30294cc28a6c27ba5ce9374bfac81cecc2",
    (_M2,
     "test_a2_02_drop_table_candidates_is_violation"):
        "1ca33362341a06eca4b19a7d66cdc47806e4f3f6ea5d9e90f0dceb336ec8d6ba",
    (_M2,
     "test_a2_03_drop_table_if_exists_quoted_epoch_is_violation"):
        "c9bd55f45bbf9c3a39d3708745cdfb976636eb385a94249a09a88580a305bc00",
    (_M2,
     "test_a2_04_drop_other_table_is_not_violation"):
        "2e79cd2517587c0010f023566406b524f1e3964801d0bec0b5d071f5c6425946",
    (_M2,
     "test_a2_05_drop_with_era_record_is_not_violation"):
        "8c9ef42f02997414dc41fd8a43287053bc4dd813d9180f3996a776992a2c8718",
    (_M2,
     "test_a2_06_drop_and_era_record_only_in_comments_is_violation"):
        "a1734942f08530ae62c8e9995f98f9b0713eeba303845ca1459df07e59f392f5",
    (_M2,
     "test_a2_07_real_migrations_scan_clean_and_names_imported"):
        "61c9b7f8658449198717e28ed57e4f15c63e30a169259580dde91979c6684135",
    (_M6,
     "test_a2_08_every_roster_id_has_exactly_one_implementing_test"):
        "847c4359bbfbce47fc5f5e7af4e89185637201030f6aa997814138c513e0a592",
    (_M6,
     "test_a2_09_six_case_functions_are_byte_unchanged"):
        "b5d8223636fc498ff2726ab941a3280518a8a347f7523f2d507679358c785309",
    (_M4,
     "test_a2_10_three_edits_of_the_v38_stored_ddl_equal_the_v39_stored_ddl"):
        "3c2e2d8acca283f04cf4749cd1b23ff71209f2f23d7111955bbc40f3845b5f14",
    (_M5,
     "test_a2_100_replay_rewritten_drops_h1_by_one_named_grown_admits_unchanged"):
        "9efc1dfb3788cc2accdcd78301287d4bb1245bca51dcc44d00cec621ed53549e",
    (_M5,
     "test_a2_101_the_predicate_closure_holds_against_the_migrated_head_schema"):
        "37f40b55237c0a258544d63fbc16f8e040be80289511dd5c615c456e5e842524",
    (_M5,
     "test_a2_102_the_22a_six_case_gate_is_byte_unchanged_on_the_final_head"):
        "b43ba16eaad5914ac397dabbddc135cd50bdabf9cd903e084a7b7bd3ad87740f",
    (_M5,
     "test_a2_103_the_tier_enum_drift_tests_hold"):
        "b30e488e9e0c07e3c3902c143a59c866d693c0b7932cc37a46710a2b02eaf61a",
    (_M5,
     "test_a2_104_the_fixture_is_the_record_in_the_real_repo"):
        "d213ec859a0ea03e67f27bdd17f69da1c76f41e5fe523c5446ffeb8b6867cb99",
    (_M4,
     "test_a2_11_edit_anchors_occur_once_and_the_seventh_column_is_last"):
        "23208ca6c29da7bd09dc210639e32eab68cf176a844101f64b49e63711e4c91d",
    (_M4,
     "test_a2_12_row_1_is_byte_identical_across_the_rebuild"):
        "33cfbb9f94dc89293ae2c59338fae1dcc5a83f0f1c850e60e67eae68906833b4",
    (_M4,
     "test_a2_13_the_sequence_is_carried_not_recomputed"):
        "499f2b67d35d6ffa293e48654e0ec1d7aac149ba9fcb186715a481598e9f4a77",
    (_M4,
     "test_a2_14_live_shape_and_zero_row_sequences"):
        "250f9b34a8282e103835d24f8c30a777ba43db4d86f09a128dcc5d019088296d",
    (_M4,
     "test_a2_15_foreign_key_check_is_empty_after_the_rebuild"):
        "125df2f906789a77b912b5264ad77ea08f946b52354453d94ae9ebaec639040f",
    (_M4,
     "test_a2_16_statement_order"):
        "e8b72015c43cd366c9f8044eefb52165cf00f5f782fecd6744b627b06c528169",
    (_M4,
     "test_a2_17_the_four_unchanged_objects_are_verbatim"):
        "83d35f9c001eb598702a97dbcc2aeffd5782b7a23bd1947773c6669650a2accb",
    (_M4,
     "test_a2_18_the_manifest_diff_is_three_changed_objects_and_nothing_else"):
        "52d9a345f38a6022b06417042b3b85e0cda1ad3166db21d67bb0a9f8cb3059e3",
    (_M4,
     "test_a2_19_the_0039_migration_yields_v39_and_its_three_objects"):
        "f98949737f60f71444fc5a93dd9e5d189dc96109eef671a19fba4c05e3efab01",
    (_M4,
     "test_a2_20_the_reversibility_header_names_the_edits_and_the_gate"):
        "ab1ddb84e424d2e06c5495855ba5220cf17c99ac9c5ca9c5f8c72162dba8e913",
    (_M4,
     "test_a2_21_the_22a2_gate_fires_and_the_cli_echoes_its_image"):
        "53a1ea5dff4af92c972e13302039f345c21dec8874ba0bd504031e32ee45494e",
    (_M3,
     "test_a2_22_the_post_base_roster_is_one_22a2_row_after_the_base_23"):
        "764883c8e59b51671006ebae771e56a9dad96092ce6f634b6a5fbe21f3c5fb48",
    (_M4,
     "test_a2_23_sql_admission_tier_check_equals_the_python_enum"):
        "eebb436873100fceefd46f7dbd9cc4e471dc650f34aa0636e96ee261e53f6106",
    (_M4,
     "test_a2_24_the_model_carries_the_three_way_paired_rule"):
        "e09e64b277fe9b737272789ef1606a39ac01069393841fc5ee5870559b23cbb8",
    (_M4,
     "test_a2_25_trigger_literals_equal_their_python_mirrors"):
        "1a2fcf419ba963b7d78e892ce72dac60a92a98323414fcd9397c7b7940494a8c",
    (_M4,
     "test_a2_26_a_truthful_tier2_row_inserts"):
        "9192c9dc0c5a21f75319126a7ed8cc47a75e1f3c44a0bc7731cf039e6a8eaf05",
    (_M4,
     "test_a2_27_a_blob_omitting_interval_is_refused_not_failed_open"):
        "ae7ce4738b0728292b7cb79aa6b2b6daaecd0f342182f618f31bcda4b4eb07e5",
    (_M4,
     "test_a2_28_each_single_mutation_of_the_truthful_row_is_refused"):
        "8e14fde610ee137366086340c90b9345c9ece5094a56fc2b1c4a7d6e33e6014e",
    (_M4,
     "test_a2_29_the_tier2_span_never_rounds_or_casts"):
        "a6ecf7d37522b51352547fe1c34545a639959826692a269c51d2ce03e52efadf",
    (_M4,
     "test_a2_30_the_latch_ladder_branch_refuses_an_escaped_or_tier2_versioned_blob"):
        "e28d4130aafa58fb00a2c0655b5f60c28e08f9509864ec612c3d1b5878bb6aa4",
    (_M4,
     "test_a2_31_the_tier2_row_is_append_only"):
        "3bbb5b4737e31ee1a41a0244dd075a754a2d2d5b30635adccd8d82c4b5ac23f8",
    (_M10,
     "test_a2_32_malformed_evidence_file_refuses_evidence_file_malformed"):
        "d4fcc918f662308fc3d76df5a76e9fbf8dabf74db6c0e58bd7da56bf66bf6349",
    (_M10,
     "test_a2_33_quoted_text_not_in_artifact"):
        "167f69ed30e735f49896a3046ed11ef7b01b408410cf295a5aeb212fee4e63ce",
    (_M10,
     "test_a2_34_quoted_text_spanning_two_lines_refuses_not_a_whole_line"):
        "d8d398dd025b4474a7f7d95b6be147006b2a5190ee0dda9c812edea3dcbfeb49",
    (_M10,
     "test_a2_35_line57_world_yields_author_instant_ancestry_and_remote_tip"):
        "a7fe8d79cc45eb3628647fea0d859ef35e77bc080f48c9737cc613076d06bbb2",
    (_M10,
     "test_a2_36_local_commit_not_ancestor_of_remote_ref_reads_false"):
        "297288c22a55bc6c4a34ede07779fc77e10b6acd4d243edf776025721e77515f",
    (_M10,
     "test_a2_37_non_ascii_line_round_trips_as_bytes"):
        "5f8e63a36c9e06d7045486b05095b938bbcbdee1f1c17fafeed33b02025a1df7",
    (_M10,
     "test_a2_38_git_timeout_reads_tier2_unverifiable_without_raising"):
        "39370e22fb6e5cbe051ceebb9bdadd4d84e8f4b3314fe8819cd4f36ffaaaa096",
    (_M10,
     "test_a2_39_no_remote_ref_reads_tier2_unverifiable"):
        "2ecf850bb601ea37ed4eda23c5a8a5ab5b3e99cfb6599e46115b5d6e08fb134c",
    (_M10,
     "test_a2_40_reflog_absent_reads_null_present_reads_age"):
        "ca158ac02cab3107fddce6de248c166ab3c9479c70c1a99ed3b0651b9a19f221",
    (_M10,
     "test_a2_41_preflight_never_raises_and_module_writes_no_db"):
        "be772237c931996d999fb64748c90e76c9dda3f95ee4331b531547ab3197023b",
    (_M8,
     "test_a2_42_trade25_admits_and_builder_equals_the_hand_built_literal"):
        "debbd93d31391cf742d5a156121792bebe0c6b6ef28ae6680455a522f9136df9",
    (_M8,
     "test_a2_43_interval_durations_and_prose_on_trade25_live_values"):
        "10b97c198379b2b14ae67150c9f3fbfc0710acc4f2b7c191a4f7ff22e5ffb69c",
    (_M8,
     "test_a2_44_not_ancestor_refuses_criterion_1"):
        "08a1d982512cee457700aae6951cbc5401f342065a0276d42fe439168f2ff095",
    (_M8,
     "test_a2_45_et_date_equal_to_fill_session_refuses"):
        "4680f43c30fea0efbb11d261d604d45c71d9804cd3d4b92fd62c63f70f3bc42b",
    (_M8,
     "test_a2_46_et_date_not_the_local_offset_date"):
        "54210323a86d81aeabc80501817bca38d8ade07f8aba6a05bfaf66cd32a0eeb8",
    (_M8,
     "test_a2_47_et_day_before_fill_passes_criterion_2"):
        "46f3cb2d6ee863a65b2d08d656f2e85332e8840c1711693ccd7dbb440d5ce5fd",
    (_M8,
     "test_a2_48_committer_date_is_never_verdict_bearing"):
        "551e9dc0805f374dc9401ec9708ba20f869188c914b79288b79d1d8a1fe403ca",
    (_M8,
     "test_a2_49_five_cent_pivot_refuses_naming_pivot"):
        "1efb1cd0b3902b8bd2132e3fe5bb03815491191c26e59b9cf8b601f0398da5fe",
    (_M8,
     "test_a2_50_eighth_dollar_pivot_admits_under_python_half_even"):
        "7e00ea6794558b4f211693417dfdb455b1a4d1fe712659d696cb6cc002a06541",
    (_M8,
     "test_a2_51_control_both_engines_render_22_12"):
        "cc6b0b20c0eaa01619af532ddb7fd65843808dbc189b11ce3ba552a0ff5844b7",
    (_M8,
     "test_a2_52_ticker_is_token_bounded"):
        "9a61863157b97a2346de78fe5f880449e10cabd0526e6f9ef706d3608388fec6",
    (_M8,
     "test_a2_53_absent_ticker_refuses_naming_ticker"):
        "1f271e13aa1fd2801846aa59d8a9512815165d652c75d8a9450eaca447fc74d3",
    (_M8,
     "test_a2_54_wrong_action_session_refuses_naming_action_session"):
        "a636cd0402bb6eae05d5b3c63de4ccb9a51bf3e6ee058462386c405d6a2dd079",
    (_M8,
     "test_a2_55_year_rule_refuses_mm_dd_for_a_prior_year_author"):
        "2a52bed43f3022551f0c1e9f9db5adf213abf8af479b5f51fc4646586cd7577b",
    (_M8,
     "test_a2_56_iso_token_carries_its_own_year"):
        "6f90b4f3dc2a849eb297f23d783efbdef22a8b8fb75426a7be379984d34c3e5c",
    (_M8,
     "test_a2_57_record_must_be_strictly_after_fire_hi"):
        "ee3f9cdd5cf69ad818d669f8551d516c12a6ec24e9ad5832a2058df7c1fb0583",
    (_M8,
     "test_a2_58_refusal_order_first_failing_field_speaks"):
        "5c17841dbdef02771b376bfa41c9d9a74d2c25140c2bc890317c6fb9cc8c79de",
    (_M8,
     "test_a2_59_declared_limits_are_pinned"):
        "a063c7124485b3ca3a66c77072f5d02ac849819fc7eaf6b96590f6b02c50a34d",
    (_M8,
     "test_a2_60_every_trigger_predicate_has_a_reached_service_check"):
        "75f99d65911d1954de9ec4fa27889faa90f090ed5b7bab1799dbf331e9b5640c",
    (_M12,
     "test_a2_61_pre_barrier_link_with_a_passing_tier2_escapes_rung_nine"):
        "e11bf046b37daced1398abc39042290743c1f49c9b40cea25e7616a68a5beb1f",
    (_M12,
     "test_a2_62_pre_barrier_link_without_tier2_is_unchanged"):
        "9f9c3b8accc69711ab17e04d8b5f532598f8e6fe9d8bb51b91b41b56579a0314",
    (_M12,
     "test_a2_63_barrier_absent_refuses_before_any_escape"):
        "204315602fde06b36963f5fcb411ad15525388d25e34585aa9246e5af9d4dd67",
    (_M12,
     "test_a2_64_stored_and_read_time_tiers_disagreeing_never_escape"):
        "5b466587f86b271fc3789b33ffabbfb842501cc2b1effbc71aeaa70d6667ff13",
    (_M12,
     "test_a2_65_the_entry_path_never_passes_the_escape"):
        "ed3e6edf662723f5dc167a2b9b1bc01bc9baf25e0df1b6a59ac1c7df5865fdf3",
    (_M12,
     "test_a2_66_evidence_with_no_escape_to_take_refuses_and_names_why"):
        "5c65775858dff9a252c2b219cf55f50ce6a1bace343630831d2379f9bbc629c2",
    (_M9,
     "test_a2_67_trade25_world_applies_as_latch_ladder_tier2"):
        "688ba96bf4adf152f87d1006de3b01318f00104a9ed9b7f02b091ff76b1e7d92",
    (_M9,
     "test_a2_68_one_stamp_is_the_column_the_evaluated_at_and_the_read_at"):
        "077473096d02affa9e12200aacca41a5924a7f3ecab57b6f866c97a26dc01126",
    (_M9,
     "test_a2_69_the_preflight_runs_before_any_transaction"):
        "7324503741ea8fce955eb9b115d520367d26a51005c01d5dbe9629dd86231f2f",
    (_M9,
     "test_a2_70_already_applied_returns_the_existing_id_with_a_note"):
        "d887e5a28a0339f789199630005aab0ab94af18d63864217f568a7f08a9c9455",
    (_M9,
     "test_a2_71_evidence_on_a_last_word_trade_refuses"):
        "f0fe84349aa8e9b75ca02d76446163e5140e85fac500a3fde69ca437afcb54f2",
    (_M9,
     "test_a2_72_a_ladder_refusal_with_evidence_says_it_was_not_consulted"):
        "da43a33007431199cb8d57c1633a058076b7c277a15e7c29bb51de9818df1d87",
    (_M9,
     "test_a2_73_evidence_failing_criterion_3_refuses_naming_the_field"):
        "ed02f613a3e5ebdff3404cb56086fc948a697ca32d6bba20cc8a83581405f75b",
    (_M9,
     "test_a2_74_dry_run_authorizes_as_apply_and_leaves_the_db_identical"):
        "a914a95326de83407b2d88c2b3ac55096f5989b024cc5314a706ccf1dd916659",
    (_M9,
     "test_a2_75_guarded_entry_points_have_exactly_their_named_callers"):
        "34d4dad4ff0e61edfb15806c4fddc098d6250dca36b234bdc977a7add7886929",
    (_M9,
     "test_a2_76_the_envelope_reading_is_written_by_apply_and_unwound_by_dry_run"):
        "db0cb83a288756bcdb118abdf00e5029816cf51280ff9cfb9e797e2579e962e7",
    (_M1,
     "test_a2_77_the_click_parameter_manifest_is_exactly_six_entries"):
        "45390d3859edc939321ba78bf3b17786f99f50ce85943b926d54aa8268ebe1e3",
    (_M1,
     "test_a2_78_both_surfaces_print_the_four_clauses_and_the_prose"):
        "68267e80489d3fcc8ab544105436620942d8485de02d9280cafdf2787b37eed7",
    (_M1,
     "test_a2_79_a_tier2_refusal_names_the_reason_and_the_field"):
        "b8a01f95069f6ca5fc44841fad8e9a0dcdf12d4faeaa6cee82e8675d0d209cf8",
    (_M1,
     "test_a2_80_help_documents_the_three_key_file_and_no_typed_values"):
        "edbfe9f21484dc11ee1af766149e202cd92a8ae9b5dfde166e9497d327ffdc09",
    (_M11,
     "test_a2_81_trade25_row_with_the_remote_unchanged_admits"):
        "aed6f8146f685c9273c72fa1918dde6156e617b5f5f89f9ba79ed2b054143abc",
    (_M11,
     "test_a2_82_rewritten_remote_reads_stale_not_ancestor"):
        "2785dbd86bcea81b68245d5f30a60ad2bb32e107568089d745cf75dd50d705fc",
    (_M11,
     "test_a2_83_grown_remote_still_admits_and_growth_is_not_compared"):
        "e20d09f6948c338170f0b52fd4bb94e42ac722bc9877af87d43d531b3aea9860",
    (_M11,
     "test_a2_84_git_timeout_and_a_missing_remote_ref_read_unverifiable"):
        "b6054e952483969aed7055b1c1443f2e51fb7e7c6255669ee2e43ef2ffa36a0f",
    (_M11,
     "test_a2_85_a_changed_current_pivot_reads_stale_naming_pivot"):
        "84a2923b2df24761006105b94acd716974017edc0470c6e9fff5dc5a56c499d5",
    (_M11,
     "test_a2_86_a_stored_verdict_bearing_value_differing_reads_key_mismatch"):
        "0a3c0557c3f19b31b8143d3886e983d135797be7ad549c0f542b70f02f9f2949",
    (_M11,
     "test_a2_87_replay_opens_no_transaction_and_writes_nothing_on_a_ro_conn"):
        "447e66681fb57f37967e75e5557024381f2d5b8bd4700860064760025178a4a8",
    (_M11,
     "test_a2_88_barrier_absent_at_read_is_an_observation_only"):
        "65559b5cb2ed5f9968564666826ed6c7e1c7027baecd37f89a1259a222c802e5",
    (_M11,
     "test_a2_89_one_replay_per_row_and_one_ref_resolution_per_invocation"):
        "1ddf99e21ff5ac97508f0b6f3054edd2cf16792cc3b0418740ef848783e9e64b",
    (_M11,
     "test_a2_90_the_drift_reader_renders_the_read_time_verdict_for_tier2_only"):
        "0f5c83b5366630eb19c31da36ca46a57729b09ea8a46a9e74d08d310b7d1c2f0",
    (_M7,
     "test_a2_91_tripwire_status_counts_from_exclusions_and_names_both"):
        "faf45ec418644fb1db66f561b7a28f4efc291df4c7594a247c77764cc01c7fec",
    (_M7,
     "test_a2_92_journal_progress_counts_from_exclusions_and_names_both"):
        "dbfa205c14f4bb18473735ef19b9b9c3cf572f80c95f527a458ba76a38424b26",
    (_M7,
     "test_a2_93_tier_surface_counts_from_exclusions_and_names_both"):
        "01653291fbb2e5e85d2f77fd3fe50636c892be1f1dd34ee5b06c5bcf3e0fecd9",
    (_M7,
     "test_a2_94_the_card_page_renders_the_line_and_zero_data_renders_none"):
        "1b36ea4673f1b5b0b9d1fbd8128ab1d087175f3a803f5a972367d11aa09b64d7",
    (_M7,
     "test_a2_95_the_tier_page_renders_the_line_and_zero_data_renders_none"):
        "85a704eeb153b1e1339e8a3493e63e28f4af4dd48818c45bb19721fd3e1c994b",
    (_M7,
     "test_a2_96_hypothesis_list_prints_the_line_once_under_its_row"):
        "9374922dc669611532b8ec4705bc72652f696d5b617d04e3cc347ec2073106a0",
    (_M7,
     "test_a2_97_unverifiable_excludes_and_names_never_admitted_on_the_stored_grade"):
        "2a606728135ba3f3f11c30ee2f9e6b68c0a86d348dd3135d2d5ecd07100eb667",
    (_M7,
     "test_a2_97b_the_web_card_on_a_slow_git_excludes_within_the_budget"):
        "e6f4025f52596a690b1457c3f70732887e00e2cf5a39e8633cbd0370e85613e2",
    (_M7,
     "test_a2_97c_the_cli_reader_on_the_same_slow_git_waits_and_admits"):
        "d5969bbab6303c49c194cdb7186ab7fafc3cba521f146e3d3f51006c4e2c0930",
    (_M5,
     "test_a2_98_trade25_admits_on_tier2_from_line57_end_to_end"):
        "5d9c826e58f7e6a932799e73d8aa0ae817444932a91c3ad534d74c61f94f4ac4",
    (_M5,
     "test_a2_99_each_clause_refuses_its_one_mutation_end_to_end"):
        "c1961d622cb57ebbedf2af854c0accdfcd9410a4ead928f3c89b9ce5a6a6cf66",
}

_REASON = "re-scoped 22-B, reason: HEAD-claim in a version-named case; ledger R0.I"

# The three NAMED exemptions: roster id -> (post-re-scope (module, fn), sha, reason).
RE_SCOPED_22B: dict[str, tuple[tuple[str, str], str, str]] = {
    "A2-18": (
        (_M4,
         "test_a2_18_the_manifest_diff_is_three_changed_objects_and_nothing_else"),
        "756d77268abcb66239a1e05559db242cd4a8374ab1c5d57cbf68148c2dbd22dd",
        _REASON),
    "A2-19": (
        (_M4,
         "test_a2_19_the_0039_migration_yields_v39_and_its_three_objects"),
        "bb068ea5a9e280e009f9e12dd5f150b205b200a04eefe4c78b4839ecca06d330",
        _REASON),
    "A2-22": (
        (_M3,
         "test_a2_22_the_post_base_roster_is_one_22a2_row_after_the_base_23"),
        "0ae6b8ee9e56d7c58405cdb838c3cb8de1e49e3b61af4754f019e742ec31e241",
        _REASON),
}


def _source_sha(module_path: str, fn_name: str) -> str:
    mod = importlib.import_module(".".join(Path(module_path).with_suffix("").parts))
    src = inspect.getsource(getattr(mod, fn_name))
    return hashlib.sha256(src.encode("utf-8")).hexdigest()


def test_the_22a2_case_functions_are_byte_unchanged_except_three_re_scoped_b22_170(
) -> None:
    found = _roster_tokens_in_tests()
    implementing: dict[str, tuple[str, str]] = {}
    for rid in CASES_22A2:
        hits = found.get(token(rid), [])
        assert len(hits) == 1, (rid, hits)
        implementing[rid] = hits[0]
    assert len(implementing) == 106
    assert set(RE_SCOPED_22B) == {"A2-18", "A2-19", "A2-22"}
    # Closure: every implementing function is pinned at base OR re-scoped.
    base_keys = set(BASE_PINS_22A2)
    for rid, key in implementing.items():
        if rid in RE_SCOPED_22B:
            assert key == RE_SCOPED_22B[rid][0], (rid, key)
        else:
            assert key in base_keys, (rid, key)
    assert len(base_keys) == 106
    drifted = [
        rid for rid, key in implementing.items()
        if rid not in RE_SCOPED_22B and _source_sha(*key) != BASE_PINS_22A2[key]
    ]
    assert not drifted, drifted
    for rid, (key, sha, reason) in RE_SCOPED_22B.items():
        assert reason == _REASON
        assert _source_sha(*key) == sha, rid
        assert BASE_PINS_22A2.get(key) != sha, (rid, "re-scope changed nothing")
