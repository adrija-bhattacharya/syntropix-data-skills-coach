import { Component, type ErrorInfo, type ReactNode } from "react";

interface Props {
  children: ReactNode;
  fallback?: (error: Error, reset: () => void) => ReactNode;
}
interface State {
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    // eslint-disable-next-line no-console
    console.error("Syntropix UI error:", error, info.componentStack);
  }

  reset = (): void => this.setState({ error: null });

  render(): ReactNode {
    const { error } = this.state;
    if (!error) return this.props.children;
    if (this.props.fallback) return this.props.fallback(error, this.reset);
    return (
      <div role="alert" className="m-space-lg p-space-lg rounded-xl bg-error-container/20 flex flex-col gap-space-sm">
        <h2 className="font-headline-sm text-headline-sm text-error">Something broke</h2>
        <p className="font-body-sm text-body-sm text-on-surface-variant">{error.message}</p>
        <button type="button" className="w-fit px-space-md py-1.5 rounded-lg bg-surface-container-high font-body-strong text-body-sm" onClick={this.reset}>
          Try again
        </button>
      </div>
    );
  }
}
