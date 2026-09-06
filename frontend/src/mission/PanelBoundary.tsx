/**
 * PanelBoundary.tsx — one panel may fail. The application may not.
 *
 * WHY THIS EXISTS
 * ---------------
 * A single uncaught throw inside one `useEffect` in `MissionMap` unmounted the
 * entire React tree and served a blank page in production. Everything else on
 * that screen was fine: layers.json, the four analysis artifacts and the
 * hillshade all returned 200, the verdict was computed, the stat bar had its
 * numbers. None of it was rendered, because React's default behaviour on an
 * unhandled error is to unmount the whole tree rather than show a broken
 * subtree.
 *
 * **On demo day a blank page is indistinguishable from a dead project.** That is
 * the entire argument for this file.
 *
 * WHAT IT IS NOT
 * --------------
 * IT IS NOT A FIX FOR THE BUG IT CAUGHT, and it must never be used as one. The
 * crash that motivated it is fixed at three levels — the wire type now declares
 * the degraded payload, `fetchMissionState` rejects it at the boundary, and the
 * effect checks the field rather than the object. This is a floor under all of
 * them, for the next one.
 *
 * WHAT IT RENDERS
 * ---------------
 * The component's name, the error message, and a NO DATA mark in that panel's
 * place. It does NOT render a friendly apology: a reader must be able to tell a
 * panel that failed from a panel that has nothing to show, and this project
 * already has a NO DATA state for the second. A caught error is a third thing
 * and says so.
 */
import { Component, type ErrorInfo, type ReactNode } from 'react';

interface Props {
  /** Shown in the fallback. Use the component's own name. */
  name: string;
  children: ReactNode;
}

interface State {
  error: Error | null;
  stack: string | null;
}

export class PanelBoundary extends Component<Props, State> {
  state: State = { error: null, stack: null };

  static getDerivedStateFromError(error: Error): Partial<State> {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    // Loud, and on the console the verification harness reads. A boundary that
    // swallows the error silently would turn a visible crash into an invisible
    // one, which is worse than the crash: the page would look merely empty.
    console.error(`[PanelBoundary] ${this.props.name} threw and was contained. `
      + 'The rest of the page is unaffected. This is a FLOOR, not a fix — the '
      + 'error below is real and must be fixed at its source.', error);
    this.setState({ stack: info.componentStack ?? null });
  }

  render() {
    if (!this.state.error) return this.props.children;
    return (
      <div className="mc-boundary" role="alert">
        <div className="mc-boundary-head">
          {this.props.name} failed
          <span className="mc-pv mc-pv--unavailable">NO DATA</span>
        </div>
        <div className="mc-boundary-msg">{this.state.error.message}</div>
        <div className="mc-boundary-note">
          This panel threw and was contained; the rest of the page is live. The
          error is real — it is shown rather than hidden, and it is not a
          measurement that is absent.
        </div>
      </div>
    );
  }
}
