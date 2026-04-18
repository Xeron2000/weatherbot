import sys
import time
import requests

from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

from . import config as _config
from . import forecasts as _forecasts
from . import paper_execution as _paper_execution
from . import persistence as _persistence
from . import polymarket as _polymarket
from . import reporting as _reporting
from . import strategy as _strategy
from .cli import main
from .domain import LOCATIONS, MONTHS, TIMEZONES
from .paths import CALIBRATION_FILE, CONFIG_FILE, DATA_DIR, MARKETS_DIR, ROOT_DIR, STATE_FILE, ensure_data_dirs


ensure_data_dirs()

_cfg = _config.load_config()

BALANCE = _cfg.get("balance", 10000.0)
MIN_VOLUME = _cfg.get("min_volume", 500)
MIN_HOURS = _cfg.get("min_hours", 2.0)
MAX_HOURS = _cfg.get("max_hours", 72.0)
KELLY_FRACTION = _cfg.get("kelly_fraction", 0.25)
MAX_SLIPPAGE = _cfg.get("max_slippage", 0.03)
SCAN_INTERVAL = _cfg.get("scan_interval", 3600)
CALIBRATION_MIN = _cfg.get("calibration_min", 30)
VC_KEY = _cfg.get("vc_key", "")

YES_STRATEGY = _cfg.get(
    "yes_strategy",
    {
        "max_price": 0.25,
        "min_probability": 0.14,
        "min_edge": 0.03,
        "min_hours": MIN_HOURS,
        "max_hours": MAX_HOURS,
        "max_size": 20.0,
        "min_size": 1.0,
    },
)

RISK_ROUTER = _config.load_risk_router_config(_cfg)
ORDER_POLICY = _config.load_order_policy_config(_cfg)
PAPER_EXECUTION = _config.load_paper_execution_config(_cfg)

MAX_BET = YES_STRATEGY.get("max_size", _cfg.get("max_bet", 20.0))
MIN_EV = _cfg.get("min_ev", 0.10)
MAX_PRICE = YES_STRATEGY.get("max_price", _cfg.get("max_price", 0.45))

SIGMA_F = 2.0
SIGMA_C = 1.2
YES_PEAK_WINDOW_END_HOUR = 15
YES_PEAK_WINDOW_NEAR_BUFFER = 1.0
YES_PEAK_WINDOW_PENALTY = 0.35
WEATHER_FRESHNESS_HOURS = 6.0
MONITOR_INTERVAL = 600

_cal = {}

_MODULES = (_config, _forecasts, _polymarket, _persistence, _strategy, _paper_execution, _reporting)
_RAW_FUNCTIONS = {}
_RAW_FUNCTIONS["load_risk_router_config"] = _config.load_risk_router_config
_RAW_FUNCTIONS["load_order_policy_config"] = _config.load_order_policy_config
_RAW_FUNCTIONS["load_paper_execution_config"] = _config.load_paper_execution_config
_RAW_FUNCTIONS["load_config"] = _config.load_config
_RAW_FUNCTIONS["get_ecmwf"] = _forecasts.get_ecmwf
_RAW_FUNCTIONS["get_hrrr"] = _forecasts.get_hrrr
_RAW_FUNCTIONS["get_metar"] = _forecasts.get_metar
_RAW_FUNCTIONS["get_actual_temp"] = _forecasts.get_actual_temp
_RAW_FUNCTIONS["check_market_resolved"] = _forecasts.check_market_resolved
_RAW_FUNCTIONS["get_polymarket_event"] = _polymarket.get_polymarket_event
_RAW_FUNCTIONS["get_market_price"] = _polymarket.get_market_price
_RAW_FUNCTIONS["parse_temp_range"] = _polymarket.parse_temp_range
_RAW_FUNCTIONS["hours_to_resolution"] = _polymarket.hours_to_resolution
_RAW_FUNCTIONS["in_bucket"] = _polymarket.in_bucket
_RAW_FUNCTIONS["parse_market_unit"] = _polymarket.parse_market_unit
_RAW_FUNCTIONS["parse_station_code"] = _polymarket.parse_station_code
_RAW_FUNCTIONS["normalize_skip_reasons"] = _polymarket.normalize_skip_reasons
_RAW_FUNCTIONS["extract_resolution_metadata"] = _polymarket.extract_resolution_metadata
_RAW_FUNCTIONS["extract_token_ids"] = _polymarket.extract_token_ids
_RAW_FUNCTIONS["build_market_contracts"] = _polymarket.build_market_contracts
_RAW_FUNCTIONS["evaluate_market_guardrails"] = _polymarket.evaluate_market_guardrails
_RAW_FUNCTIONS["safe_float"] = _polymarket.safe_float
_RAW_FUNCTIONS["get_clob_book"] = _polymarket.get_clob_book
_RAW_FUNCTIONS["get_clob_tick_size"] = _polymarket.get_clob_tick_size
_RAW_FUNCTIONS["get_token_quote_snapshot"] = _polymarket.get_token_quote_snapshot
_RAW_FUNCTIONS["build_quote_snapshot"] = _polymarket.build_quote_snapshot
_RAW_FUNCTIONS["quote_for_side"] = _polymarket.quote_for_side
_RAW_FUNCTIONS["load_cal"] = _persistence.load_cal
_RAW_FUNCTIONS["get_sigma"] = _persistence.get_sigma
_RAW_FUNCTIONS["run_calibration"] = _persistence.run_calibration
_RAW_FUNCTIONS["market_path"] = _persistence.market_path
_RAW_FUNCTIONS["load_market"] = _persistence.load_market
_RAW_FUNCTIONS["save_market"] = _persistence.save_market
_RAW_FUNCTIONS["load_all_markets"] = _persistence.load_all_markets
_RAW_FUNCTIONS["new_market"] = _persistence.new_market
_RAW_FUNCTIONS["load_state"] = _persistence.load_state
_RAW_FUNCTIONS["save_state"] = _persistence.save_state
_RAW_FUNCTIONS["norm_cdf"] = _strategy.norm_cdf
_RAW_FUNCTIONS["bucket_prob"] = _strategy.bucket_prob
_RAW_FUNCTIONS["normalize_probability_weights"] = _strategy.normalize_probability_weights
_RAW_FUNCTIONS["get_local_now"] = _strategy.get_local_now
_RAW_FUNCTIONS["assess_yes_peak_window_penalty"] = _strategy.assess_yes_peak_window_penalty
_RAW_FUNCTIONS["get_source_sigma"] = _strategy.get_source_sigma
_RAW_FUNCTIONS["aggregate_probability"] = _strategy.aggregate_probability
_RAW_FUNCTIONS["calc_ev"] = _strategy.calc_ev
_RAW_FUNCTIONS["calc_kelly"] = _strategy.calc_kelly
_RAW_FUNCTIONS["bet_size"] = _strategy.bet_size
_RAW_FUNCTIONS["strategy_hours_ok"] = _strategy.strategy_hours_ok
_RAW_FUNCTIONS["determine_size_multiplier"] = _strategy.determine_size_multiplier
_RAW_FUNCTIONS["evaluate_yes_candidate"] = _strategy.evaluate_yes_candidate
_RAW_FUNCTIONS["evaluate_no_candidate"] = _strategy.evaluate_no_candidate
_RAW_FUNCTIONS["build_candidate_assessments"] = _strategy.build_candidate_assessments
_RAW_FUNCTIONS["missing_strategy_fields"] = _strategy.missing_strategy_fields
_RAW_FUNCTIONS["normalize_route_reason_codes"] = _strategy.normalize_route_reason_codes
_RAW_FUNCTIONS["strategy_for_leg"] = _strategy.strategy_for_leg
_RAW_FUNCTIONS["candidate_worst_loss"] = _strategy.candidate_worst_loss
_RAW_FUNCTIONS["assessment_liquidity"] = _strategy.assessment_liquidity
_RAW_FUNCTIONS["sort_leg_candidates"] = _strategy.sort_leg_candidates
_RAW_FUNCTIONS["build_exposure_keys"] = _strategy.build_exposure_keys
_RAW_FUNCTIONS["route_candidate_assessment"] = _strategy.route_candidate_assessment
_RAW_FUNCTIONS["build_leg_risk_state"] = _strategy.build_leg_risk_state
_RAW_FUNCTIONS["build_empty_risk_state"] = _strategy.build_empty_risk_state
_RAW_FUNCTIONS["apply_reservation_to_risk_state"] = _strategy.apply_reservation_to_risk_state
_RAW_FUNCTIONS["remove_reservation_from_risk_state"] = _strategy.remove_reservation_from_risk_state
_RAW_FUNCTIONS["assessment_matches_reservation"] = _strategy.assessment_matches_reservation
_RAW_FUNCTIONS["release_reserved_exposure"] = _strategy.release_reserved_exposure
_RAW_FUNCTIONS["restore_risk_state_from_markets"] = _strategy.restore_risk_state_from_markets
_RAW_FUNCTIONS["build_reserved_exposure"] = _strategy.build_reserved_exposure
_RAW_FUNCTIONS["take_forecast_snapshot"] = _strategy.take_forecast_snapshot
_RAW_FUNCTIONS["scan_and_update"] = _strategy.scan_and_update
_RAW_FUNCTIONS["monitor_positions"] = _strategy.monitor_positions
_RAW_FUNCTIONS["refresh_active_order_quotes"] = _strategy.refresh_active_order_quotes
_RAW_FUNCTIONS["monitor_active_orders"] = _strategy.monitor_active_orders
_RAW_FUNCTIONS["run_loop"] = _strategy.run_loop
_RAW_FUNCTIONS["find_assessment_for_reservation"] = _paper_execution.find_assessment_for_reservation
_RAW_FUNCTIONS["find_quote_for_market"] = _paper_execution.find_quote_for_market
_RAW_FUNCTIONS["resolve_market_id_for_range"] = _paper_execution.resolve_market_id_for_range
_RAW_FUNCTIONS["compute_passive_limit_price"] = _paper_execution.compute_passive_limit_price
_RAW_FUNCTIONS["build_passive_order_intent"] = _paper_execution.build_passive_order_intent
_RAW_FUNCTIONS["apply_order_transition"] = _paper_execution.apply_order_transition
_RAW_FUNCTIONS["is_order_terminal"] = _paper_execution.is_order_terminal
_RAW_FUNCTIONS["is_order_unfinished"] = _paper_execution.is_order_unfinished
_RAW_FUNCTIONS["build_empty_paper_execution_state"] = _paper_execution.build_empty_paper_execution_state
_RAW_FUNCTIONS["ensure_market_paper_execution_defaults"] = _paper_execution.ensure_market_paper_execution_defaults
_RAW_FUNCTIONS["ensure_market_order_defaults"] = _paper_execution.ensure_market_order_defaults
_RAW_FUNCTIONS["parse_simulation_ts"] = _paper_execution.parse_simulation_ts
_RAW_FUNCTIONS["add_ms_to_ts"] = _paper_execution.add_ms_to_ts
_RAW_FUNCTIONS["build_paper_execution_state"] = _paper_execution.build_paper_execution_state
_RAW_FUNCTIONS["record_execution_event"] = _paper_execution.record_execution_event
_RAW_FUNCTIONS["finalize_paper_step"] = _paper_execution.finalize_paper_step
_RAW_FUNCTIONS["simulate_paper_execution_step"] = _paper_execution.simulate_paper_execution_step
_RAW_FUNCTIONS["build_order_restore_entry"] = _paper_execution.build_order_restore_entry
_RAW_FUNCTIONS["restore_order_state_from_markets"] = _paper_execution.restore_order_state_from_markets
_RAW_FUNCTIONS["find_route_for_reservation"] = _paper_execution.find_route_for_reservation
_RAW_FUNCTIONS["archive_order"] = _paper_execution.archive_order
_RAW_FUNCTIONS["average_order_fill_price"] = _paper_execution.average_order_fill_price
_RAW_FUNCTIONS["build_position_from_order"] = _paper_execution.build_position_from_order
_RAW_FUNCTIONS["maybe_release_order_reservation"] = _paper_execution.maybe_release_order_reservation
_RAW_FUNCTIONS["transition_order_terminal"] = _paper_execution.transition_order_terminal
_RAW_FUNCTIONS["sync_active_order_with_paper_engine"] = _paper_execution.sync_active_order_with_paper_engine
_RAW_FUNCTIONS["sync_market_order"] = _paper_execution.sync_market_order
_RAW_FUNCTIONS["route_market_candidates"] = _paper_execution.route_market_candidates
_RAW_FUNCTIONS["reconcile_market_reservation"] = _paper_execution.reconcile_market_reservation
_RAW_FUNCTIONS["format_bucket_label"] = _reporting.format_bucket_label
_RAW_FUNCTIONS["format_resolution_text"] = _reporting.format_resolution_text
_RAW_FUNCTIONS["format_quote_context"] = _reporting.format_quote_context
_RAW_FUNCTIONS["print_candidate_assessments"] = _reporting.print_candidate_assessments
_RAW_FUNCTIONS["print_scan_summary"] = _reporting.print_scan_summary
_RAW_FUNCTIONS["print_risk_summary"] = _reporting.print_risk_summary
_RAW_FUNCTIONS["print_exposure_summary"] = _reporting.print_exposure_summary
_RAW_FUNCTIONS["print_route_decision_summary"] = _reporting.print_route_decision_summary
_RAW_FUNCTIONS["format_order_reason_counts"] = _reporting.format_order_reason_counts
_RAW_FUNCTIONS["collect_active_order_facts"] = _reporting.collect_active_order_facts
_RAW_FUNCTIONS["collect_recent_terminal_orders"] = _reporting.collect_recent_terminal_orders
_RAW_FUNCTIONS["summarize_terminal_order_reasons"] = _reporting.summarize_terminal_order_reasons
_RAW_FUNCTIONS["replay_order_sort_key"] = _reporting.replay_order_sort_key
_RAW_FUNCTIONS["collect_replay_orders"] = _reporting.collect_replay_orders
_RAW_FUNCTIONS["events_for_order"] = _reporting.events_for_order
_RAW_FUNCTIONS["parse_iso_or_none"] = _reporting.parse_iso_or_none
_RAW_FUNCTIONS["delta_ms"] = _reporting.delta_ms
_RAW_FUNCTIONS["first_event_by_type"] = _reporting.first_event_by_type
_RAW_FUNCTIONS["count_adverse_buffer_hits"] = _reporting.count_adverse_buffer_hits
_RAW_FUNCTIONS["build_replay_fill_quality"] = _reporting.build_replay_fill_quality
_RAW_FUNCTIONS["format_replay_quality"] = _reporting.format_replay_quality
_RAW_FUNCTIONS["format_replay_event_line"] = _reporting.format_replay_event_line
_RAW_FUNCTIONS["print_replay"] = _reporting.print_replay
_RAW_FUNCTIONS["print_order_summary"] = _reporting.print_order_summary
_RAW_FUNCTIONS["print_status"] = _reporting.print_status
_RAW_FUNCTIONS["print_report"] = _reporting.print_report

SHARED_NAMES = ['_cfg', '_cal', 'requests', 'time', 'datetime', 'timezone', 'timedelta', 'ZoneInfo', 'sys', 'BALANCE', 'MIN_VOLUME', 'MIN_HOURS', 'MAX_HOURS', 'KELLY_FRACTION', 'MAX_SLIPPAGE', 'SCAN_INTERVAL', 'CALIBRATION_MIN', 'VC_KEY', 'YES_STRATEGY', 'RISK_ROUTER', 'ORDER_POLICY', 'PAPER_EXECUTION', 'MAX_BET', 'MIN_EV', 'MAX_PRICE', 'SIGMA_F', 'SIGMA_C', 'YES_PEAK_WINDOW_END_HOUR', 'YES_PEAK_WINDOW_NEAR_BUFFER', 'YES_PEAK_WINDOW_PENALTY', 'WEATHER_FRESHNESS_HOURS', 'MONITOR_INTERVAL', 'DATA_DIR', 'STATE_FILE', 'MARKETS_DIR', 'CALIBRATION_FILE', 'LOCATIONS', 'TIMEZONES', 'MONTHS', 'load_risk_router_config', 'load_order_policy_config', 'load_paper_execution_config', 'load_config', 'get_ecmwf', 'get_hrrr', 'get_metar', 'get_actual_temp', 'check_market_resolved', 'get_polymarket_event', 'get_market_price', 'parse_temp_range', 'hours_to_resolution', 'in_bucket', 'parse_market_unit', 'parse_station_code', 'normalize_skip_reasons', 'extract_resolution_metadata', 'extract_token_ids', 'build_market_contracts', 'evaluate_market_guardrails', 'safe_float', 'get_clob_book', 'get_clob_tick_size', 'get_token_quote_snapshot', 'build_quote_snapshot', 'quote_for_side', 'load_cal', 'get_sigma', 'run_calibration', 'market_path', 'load_market', 'save_market', 'load_all_markets', 'new_market', 'load_state', 'save_state', 'norm_cdf', 'bucket_prob', 'normalize_probability_weights', 'get_local_now', 'assess_yes_peak_window_penalty', 'get_source_sigma', 'aggregate_probability', 'calc_ev', 'calc_kelly', 'bet_size', 'strategy_hours_ok', 'determine_size_multiplier', 'evaluate_yes_candidate', 'evaluate_no_candidate', 'build_candidate_assessments', 'missing_strategy_fields', 'normalize_route_reason_codes', 'strategy_for_leg', 'candidate_worst_loss', 'assessment_liquidity', 'sort_leg_candidates', 'build_exposure_keys', 'route_candidate_assessment', 'build_leg_risk_state', 'build_empty_risk_state', 'apply_reservation_to_risk_state', 'remove_reservation_from_risk_state', 'assessment_matches_reservation', 'release_reserved_exposure', 'restore_risk_state_from_markets', 'build_reserved_exposure', 'take_forecast_snapshot', 'scan_and_update', 'monitor_positions', 'refresh_active_order_quotes', 'monitor_active_orders', 'run_loop', 'find_assessment_for_reservation', 'find_quote_for_market', 'resolve_market_id_for_range', 'compute_passive_limit_price', 'build_passive_order_intent', 'apply_order_transition', 'is_order_terminal', 'is_order_unfinished', 'build_empty_paper_execution_state', 'ensure_market_paper_execution_defaults', 'ensure_market_order_defaults', 'parse_simulation_ts', 'add_ms_to_ts', 'build_paper_execution_state', 'record_execution_event', 'finalize_paper_step', 'simulate_paper_execution_step', 'build_order_restore_entry', 'restore_order_state_from_markets', 'find_route_for_reservation', 'archive_order', 'average_order_fill_price', 'build_position_from_order', 'maybe_release_order_reservation', 'transition_order_terminal', 'sync_active_order_with_paper_engine', 'sync_market_order', 'route_market_candidates', 'reconcile_market_reservation', 'format_bucket_label', 'format_resolution_text', 'format_quote_context', 'print_candidate_assessments', 'print_scan_summary', 'print_risk_summary', 'print_exposure_summary', 'print_route_decision_summary', 'format_order_reason_counts', 'collect_active_order_facts', 'collect_recent_terminal_orders', 'summarize_terminal_order_reasons', 'replay_order_sort_key', 'collect_replay_orders', 'events_for_order', 'parse_iso_or_none', 'delta_ms', 'first_event_by_type', 'count_adverse_buffer_hits', 'build_replay_fill_quality', 'format_replay_quality', 'format_replay_event_line', 'print_replay', 'print_order_summary', 'print_status', 'print_report']


def _sync_runtime():
    for module in _MODULES:
        for name in SHARED_NAMES:
            if name in globals():
                setattr(module, name, globals()[name])


def _wrap(name):
    raw = _RAW_FUNCTIONS[name]

    def wrapper(*args, **kwargs):
        global _cal
        _sync_runtime()
        result = raw(*args, **kwargs)
        if hasattr(_strategy, "_cal"):
            _cal = _strategy._cal
        if hasattr(_persistence, "_cal"):
            _cal = _persistence._cal
        return result

    wrapper.__name__ = name
    wrapper.__qualname__ = name
    return wrapper


load_risk_router_config = _wrap("load_risk_router_config")
load_order_policy_config = _wrap("load_order_policy_config")
load_paper_execution_config = _wrap("load_paper_execution_config")
load_config = _wrap("load_config")
get_ecmwf = _wrap("get_ecmwf")
get_hrrr = _wrap("get_hrrr")
get_metar = _wrap("get_metar")
get_actual_temp = _wrap("get_actual_temp")
check_market_resolved = _wrap("check_market_resolved")
get_polymarket_event = _wrap("get_polymarket_event")
get_market_price = _wrap("get_market_price")
parse_temp_range = _wrap("parse_temp_range")
hours_to_resolution = _wrap("hours_to_resolution")
in_bucket = _wrap("in_bucket")
parse_market_unit = _wrap("parse_market_unit")
parse_station_code = _wrap("parse_station_code")
normalize_skip_reasons = _wrap("normalize_skip_reasons")
extract_resolution_metadata = _wrap("extract_resolution_metadata")
extract_token_ids = _wrap("extract_token_ids")
build_market_contracts = _wrap("build_market_contracts")
evaluate_market_guardrails = _wrap("evaluate_market_guardrails")
safe_float = _wrap("safe_float")
get_clob_book = _wrap("get_clob_book")
get_clob_tick_size = _wrap("get_clob_tick_size")
get_token_quote_snapshot = _wrap("get_token_quote_snapshot")
build_quote_snapshot = _wrap("build_quote_snapshot")
quote_for_side = _wrap("quote_for_side")
load_cal = _wrap("load_cal")
get_sigma = _wrap("get_sigma")
run_calibration = _wrap("run_calibration")
market_path = _wrap("market_path")
load_market = _wrap("load_market")
save_market = _wrap("save_market")
load_all_markets = _wrap("load_all_markets")
new_market = _wrap("new_market")
load_state = _wrap("load_state")
save_state = _wrap("save_state")
norm_cdf = _wrap("norm_cdf")
bucket_prob = _wrap("bucket_prob")
normalize_probability_weights = _wrap("normalize_probability_weights")
get_local_now = _wrap("get_local_now")
assess_yes_peak_window_penalty = _wrap("assess_yes_peak_window_penalty")
get_source_sigma = _wrap("get_source_sigma")
aggregate_probability = _wrap("aggregate_probability")
calc_ev = _wrap("calc_ev")
calc_kelly = _wrap("calc_kelly")
bet_size = _wrap("bet_size")
strategy_hours_ok = _wrap("strategy_hours_ok")
determine_size_multiplier = _wrap("determine_size_multiplier")
evaluate_yes_candidate = _wrap("evaluate_yes_candidate")
evaluate_no_candidate = _wrap("evaluate_no_candidate")
build_candidate_assessments = _wrap("build_candidate_assessments")
missing_strategy_fields = _wrap("missing_strategy_fields")
normalize_route_reason_codes = _wrap("normalize_route_reason_codes")
strategy_for_leg = _wrap("strategy_for_leg")
candidate_worst_loss = _wrap("candidate_worst_loss")
assessment_liquidity = _wrap("assessment_liquidity")
sort_leg_candidates = _wrap("sort_leg_candidates")
build_exposure_keys = _wrap("build_exposure_keys")
route_candidate_assessment = _wrap("route_candidate_assessment")
build_leg_risk_state = _wrap("build_leg_risk_state")
build_empty_risk_state = _wrap("build_empty_risk_state")
apply_reservation_to_risk_state = _wrap("apply_reservation_to_risk_state")
remove_reservation_from_risk_state = _wrap("remove_reservation_from_risk_state")
assessment_matches_reservation = _wrap("assessment_matches_reservation")
release_reserved_exposure = _wrap("release_reserved_exposure")
restore_risk_state_from_markets = _wrap("restore_risk_state_from_markets")
build_reserved_exposure = _wrap("build_reserved_exposure")
take_forecast_snapshot = _wrap("take_forecast_snapshot")
scan_and_update = _wrap("scan_and_update")
monitor_positions = _wrap("monitor_positions")
refresh_active_order_quotes = _wrap("refresh_active_order_quotes")
monitor_active_orders = _wrap("monitor_active_orders")
run_loop = _wrap("run_loop")
find_assessment_for_reservation = _wrap("find_assessment_for_reservation")
find_quote_for_market = _wrap("find_quote_for_market")
resolve_market_id_for_range = _wrap("resolve_market_id_for_range")
compute_passive_limit_price = _wrap("compute_passive_limit_price")
build_passive_order_intent = _wrap("build_passive_order_intent")
apply_order_transition = _wrap("apply_order_transition")
is_order_terminal = _wrap("is_order_terminal")
is_order_unfinished = _wrap("is_order_unfinished")
build_empty_paper_execution_state = _wrap("build_empty_paper_execution_state")
ensure_market_paper_execution_defaults = _wrap("ensure_market_paper_execution_defaults")
ensure_market_order_defaults = _wrap("ensure_market_order_defaults")
parse_simulation_ts = _wrap("parse_simulation_ts")
add_ms_to_ts = _wrap("add_ms_to_ts")
build_paper_execution_state = _wrap("build_paper_execution_state")
record_execution_event = _wrap("record_execution_event")
finalize_paper_step = _wrap("finalize_paper_step")
simulate_paper_execution_step = _wrap("simulate_paper_execution_step")
build_order_restore_entry = _wrap("build_order_restore_entry")
restore_order_state_from_markets = _wrap("restore_order_state_from_markets")
find_route_for_reservation = _wrap("find_route_for_reservation")
archive_order = _wrap("archive_order")
average_order_fill_price = _wrap("average_order_fill_price")
build_position_from_order = _wrap("build_position_from_order")
maybe_release_order_reservation = _wrap("maybe_release_order_reservation")
transition_order_terminal = _wrap("transition_order_terminal")
sync_active_order_with_paper_engine = _wrap("sync_active_order_with_paper_engine")
sync_market_order = _wrap("sync_market_order")
route_market_candidates = _wrap("route_market_candidates")
reconcile_market_reservation = _wrap("reconcile_market_reservation")
format_bucket_label = _wrap("format_bucket_label")
format_resolution_text = _wrap("format_resolution_text")
format_quote_context = _wrap("format_quote_context")
print_candidate_assessments = _wrap("print_candidate_assessments")
print_scan_summary = _wrap("print_scan_summary")
print_risk_summary = _wrap("print_risk_summary")
print_exposure_summary = _wrap("print_exposure_summary")
print_route_decision_summary = _wrap("print_route_decision_summary")
format_order_reason_counts = _wrap("format_order_reason_counts")
collect_active_order_facts = _wrap("collect_active_order_facts")
collect_recent_terminal_orders = _wrap("collect_recent_terminal_orders")
summarize_terminal_order_reasons = _wrap("summarize_terminal_order_reasons")
replay_order_sort_key = _wrap("replay_order_sort_key")
collect_replay_orders = _wrap("collect_replay_orders")
events_for_order = _wrap("events_for_order")
parse_iso_or_none = _wrap("parse_iso_or_none")
delta_ms = _wrap("delta_ms")
first_event_by_type = _wrap("first_event_by_type")
count_adverse_buffer_hits = _wrap("count_adverse_buffer_hits")
build_replay_fill_quality = _wrap("build_replay_fill_quality")
format_replay_quality = _wrap("format_replay_quality")
format_replay_event_line = _wrap("format_replay_event_line")
print_replay = _wrap("print_replay")
print_order_summary = _wrap("print_order_summary")
print_status = _wrap("print_status")
print_report = _wrap("print_report")
load_config = _wrap("load_config")
load_risk_router_config = _wrap("load_risk_router_config")
load_order_policy_config = _wrap("load_order_policy_config")
load_paper_execution_config = _wrap("load_paper_execution_config")

__all__ = ['ROOT_DIR', 'CONFIG_FILE', 'DATA_DIR', 'STATE_FILE', 'MARKETS_DIR', 'CALIBRATION_FILE', 'ensure_data_dirs', '_cfg', '_cal', 'requests', 'time', 'datetime', 'timezone', 'timedelta', 'ZoneInfo', 'sys', 'BALANCE', 'MIN_VOLUME', 'MIN_HOURS', 'MAX_HOURS', 'KELLY_FRACTION', 'MAX_SLIPPAGE', 'SCAN_INTERVAL', 'CALIBRATION_MIN', 'VC_KEY', 'YES_STRATEGY', 'RISK_ROUTER', 'ORDER_POLICY', 'PAPER_EXECUTION', 'MAX_BET', 'MIN_EV', 'MAX_PRICE', 'SIGMA_F', 'SIGMA_C', 'YES_PEAK_WINDOW_END_HOUR', 'YES_PEAK_WINDOW_NEAR_BUFFER', 'YES_PEAK_WINDOW_PENALTY', 'WEATHER_FRESHNESS_HOURS', 'MONITOR_INTERVAL', 'LOCATIONS', 'TIMEZONES', 'MONTHS', 'main', 'load_risk_router_config', 'load_order_policy_config', 'load_paper_execution_config', 'load_config', 'get_ecmwf', 'get_hrrr', 'get_metar', 'get_actual_temp', 'check_market_resolved', 'get_polymarket_event', 'get_market_price', 'parse_temp_range', 'hours_to_resolution', 'in_bucket', 'parse_market_unit', 'parse_station_code', 'normalize_skip_reasons', 'extract_resolution_metadata', 'extract_token_ids', 'build_market_contracts', 'evaluate_market_guardrails', 'safe_float', 'get_clob_book', 'get_clob_tick_size', 'get_token_quote_snapshot', 'build_quote_snapshot', 'quote_for_side', 'load_cal', 'get_sigma', 'run_calibration', 'market_path', 'load_market', 'save_market', 'load_all_markets', 'new_market', 'load_state', 'save_state', 'norm_cdf', 'bucket_prob', 'normalize_probability_weights', 'get_local_now', 'assess_yes_peak_window_penalty', 'get_source_sigma', 'aggregate_probability', 'calc_ev', 'calc_kelly', 'bet_size', 'strategy_hours_ok', 'determine_size_multiplier', 'evaluate_yes_candidate', 'evaluate_no_candidate', 'build_candidate_assessments', 'missing_strategy_fields', 'normalize_route_reason_codes', 'strategy_for_leg', 'candidate_worst_loss', 'assessment_liquidity', 'sort_leg_candidates', 'build_exposure_keys', 'route_candidate_assessment', 'build_leg_risk_state', 'build_empty_risk_state', 'apply_reservation_to_risk_state', 'remove_reservation_from_risk_state', 'assessment_matches_reservation', 'release_reserved_exposure', 'restore_risk_state_from_markets', 'build_reserved_exposure', 'take_forecast_snapshot', 'scan_and_update', 'monitor_positions', 'refresh_active_order_quotes', 'monitor_active_orders', 'run_loop', 'find_assessment_for_reservation', 'find_quote_for_market', 'resolve_market_id_for_range', 'compute_passive_limit_price', 'build_passive_order_intent', 'apply_order_transition', 'is_order_terminal', 'is_order_unfinished', 'build_empty_paper_execution_state', 'ensure_market_paper_execution_defaults', 'ensure_market_order_defaults', 'parse_simulation_ts', 'add_ms_to_ts', 'build_paper_execution_state', 'record_execution_event', 'finalize_paper_step', 'simulate_paper_execution_step', 'build_order_restore_entry', 'restore_order_state_from_markets', 'find_route_for_reservation', 'archive_order', 'average_order_fill_price', 'build_position_from_order', 'maybe_release_order_reservation', 'transition_order_terminal', 'sync_active_order_with_paper_engine', 'sync_market_order', 'route_market_candidates', 'reconcile_market_reservation', 'format_bucket_label', 'format_resolution_text', 'format_quote_context', 'print_candidate_assessments', 'print_scan_summary', 'print_risk_summary', 'print_exposure_summary', 'print_route_decision_summary', 'format_order_reason_counts', 'collect_active_order_facts', 'collect_recent_terminal_orders', 'summarize_terminal_order_reasons', 'replay_order_sort_key', 'collect_replay_orders', 'events_for_order', 'parse_iso_or_none', 'delta_ms', 'first_event_by_type', 'count_adverse_buffer_hits', 'build_replay_fill_quality', 'format_replay_quality', 'format_replay_event_line', 'print_replay', 'print_order_summary', 'print_status', 'print_report', 'load_config', 'load_risk_router_config', 'load_order_policy_config', 'load_paper_execution_config']
