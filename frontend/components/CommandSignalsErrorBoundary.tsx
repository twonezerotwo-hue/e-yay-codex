"use client";

/**
 * FAZ 17 — Command Signals Error Boundary.
 * Cards visual layer crash ederse legacy AssetGrid'e dönmek için kullanılır.
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

export default class CommandSignalsErrorBoundary extends Component<Props, State> {
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
