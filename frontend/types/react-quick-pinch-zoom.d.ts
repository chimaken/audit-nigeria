declare module "react-quick-pinch-zoom" {
  import type { ReactNode } from "react";

  export interface UpdateAction {
    x: number;
    y: number;
    scale: number;
  }

  export function make3dTransformValue(opts: { x: number; y: number; scale: number }): string;

  interface QuickPinchZoomProps {
    children: ReactNode;
    className?: string;
    onUpdate?: (action: UpdateAction) => void;
  }

  export default function QuickPinchZoom(props: QuickPinchZoomProps): JSX.Element;
}
