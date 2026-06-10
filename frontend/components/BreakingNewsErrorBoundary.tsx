"use client";

/**
 * FAZ 15 — Breaking News Error Boundary.
 *
 * Radar visual layer crash ederse legacy haber listesini göstermek için
 * Shell'in radar kısmını sarar.
 */
import { Component, type ReactNode } from "react";

interface Props {
  fallback: ReactNode;
  onError?: (err: Error) => void;
  children:  ReactNode;
}

interface State {
  hasError: boolean;
}

export default class BreakingNewsErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false };

  static getDerivedStateFromError(): State {
    return { hasError: true };
  }

  componentDidCatch(error: Error): void {
    if (this.props.onError) this.props.onError(error);
  }

  render(): ReactNode {
    if (this.state.hasError) return this.props.fallback;
    return this.props.children;
  }
}
