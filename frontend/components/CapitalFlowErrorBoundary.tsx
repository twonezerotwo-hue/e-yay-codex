"use client";

/**
 * FAZ 14 — Capital Flow Error Boundary.
 *
 * Animated visual layer crash ederse legacy fallback'i göstermesi için
 * Shell'in animated kısmını sarar.
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

export default class CapitalFlowErrorBoundary extends Component<Props, State> {
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
