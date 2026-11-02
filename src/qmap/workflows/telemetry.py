"""Optional semantic instrumentation for QMAP/QHEAT workflows.

Application annotations describe structure, not QELF pattern labels. The
reference manifest is kept separate from the inference-facing event stream.
"""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any, Callable, Iterator
from uuid import uuid4

_active_span: ContextVar[str | None] = ContextVar('qmap_qelf_span', default=None)


@dataclass
class SemanticTelemetry:
    """Lightweight recorder. Set emit=None to turn semantic hooks off.

    emit(event_name, **fields) is provided by the workflow trace writer.
    """
    emit: Callable[..., None] | None = None

    def event(self, name: str, **attributes: Any) -> None:
        if self.emit is not None:
            self.emit('semantic_event', semantic_name=name,
                      parent_span_id=_active_span.get(), attributes=attributes)

    @contextmanager
    def span(self, name: str, **attributes: Any) -> Iterator[str]:
        span_id = str(uuid4())
        parent_id = _active_span.get()
        token = _active_span.set(span_id)
        if self.emit is not None:
            self.emit('semantic_span_started', semantic_name=name,
                      span_id=span_id, parent_span_id=parent_id,
                      attributes=attributes)
        try:
            yield span_id
        except BaseException as exc:
            if self.emit is not None:
                self.emit('semantic_span_failed', semantic_name=name,
                          span_id=span_id, parent_span_id=parent_id,
                          error_type=type(exc).__name__)
            raise
        else:
            if self.emit is not None:
                self.emit('semantic_span_completed', semantic_name=name,
                          span_id=span_id, parent_span_id=parent_id)
        finally:
            _active_span.reset(token)


def qtes_semantics(*, num_qubits: int, shots: int,
                   trotter_steps: int = 3, evolution_time: float = 1.0,
                   j_coupling: float = 1.0, h_field: float = 0.7) -> dict[str, Any]:
    """Describe the current QHEAT QTES default circuit, not an individual step as a job."""
    return {'kernel_type': 'trotter_ising_1d', 'num_qubits': num_qubits,
            'shots_per_circuit': shots, 'trotter_step_count': trotter_steps,
            'evolution_time': evolution_time, 'j_coupling': j_coupling,
            'h_field': h_field, 'execution_granularity': 'single_circuit',
            'trotter_steps_are_internal_to_circuit': True}
