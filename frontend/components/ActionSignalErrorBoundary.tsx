"use client";

/**
 * FAZ 20 — Action Signal Error Boundary.
 * Race layer crash ederse legacy DecisionBanner'a düşmek için kullanılır.
 */
import { Component, type ReactNode } from "react";

interface Props {
  fallback: ReactNode;
  onError?: (err: Error) => void;
  children: ReactNode;
}

interface State {
  hasError: boolean;
}

export default class ActionSignalErrorBoundary extends Component<Props, State> {
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
