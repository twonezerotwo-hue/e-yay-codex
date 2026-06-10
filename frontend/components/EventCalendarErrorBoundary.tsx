"use client";

/**
 * FAZ 19 — Event Calendar Error Boundary.
 * 3D layer crash ederse legacy CatalystSidebar'a dönmek için kullanılır.
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

export default class EventCalendarErrorBoundary extends Component<Props, State> {
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
