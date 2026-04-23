declare module "react-quick-pinch-zoom" {
  import type { ReactNode } from "react";

  interface QuickPinchZoomProps {
    children: ReactNode;
    className?: string;
  }

  export default function QuickPinchZoom(props: QuickPinchZoomProps): JSX.Element;
}
