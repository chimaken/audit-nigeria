"use client";

import type { ProofImage } from "@/lib/types";
import { AnimatePresence, motion } from "framer-motion";
import { ChevronLeft, ChevronRight, ZoomIn } from "lucide-react";
import { useCallback, useRef, useState } from "react";
import QuickPinchZoom, { make3dTransformValue, type UpdateAction } from "react-quick-pinch-zoom";
import { Button } from "@/components/ui/button";

export function ProofGallery({ images }: { images: ProofImage[] }) {
  const [idx, setIdx] = useState(0);
  const imgRef = useRef<HTMLImageElement>(null);
  const cur = images[idx];

  const onPinchUpdate = useCallback(({ x, y, scale }: UpdateAction) => {
    const img = imgRef.current;
    if (img) {
      img.style.setProperty("transform", make3dTransformValue({ x, y, scale }));
    }
  }, []);

  const next = useCallback(() => {
    setIdx((i) => (images.length ? (i + 1) % images.length : 0));
  }, [images.length]);
  const prev = useCallback(() => {
    setIdx((i) => (images.length ? (i - 1 + images.length) % images.length : 0));
  }, [images.length]);

  if (!images.length) {
    return (
      <div className="flex h-64 items-center justify-center rounded-lg border border-dashed border-slate-700 text-sm text-slate-500">
        No proof images yet.
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-sm text-slate-400">
          <ZoomIn className="h-4 w-4 text-emerald-400" />
          Deep zoom: pinch / scroll on image
        </div>
        <span className="font-mono text-xs text-slate-500">
          {idx + 1} / {images.length}
        </span>
      </div>
      <div className="relative overflow-hidden rounded-xl border border-command-border bg-black/40">
        <AnimatePresence mode="wait">
          <motion.div
            key={cur.upload_id}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="relative flex max-h-[70vh] min-h-[240px] items-center justify-center bg-slate-950"
          >
            <QuickPinchZoom onUpdate={onPinchUpdate}>
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                ref={imgRef}
                src={cur.image_url}
                alt="EC8A proof"
                className="max-h-[70vh] w-auto max-w-full select-none object-contain"
                draggable={false}
              />
            </QuickPinchZoom>
          </motion.div>
        </AnimatePresence>
        <div className="absolute inset-y-0 left-2 flex items-center">
          <Button type="button" variant="ghost" className="h-10 w-10 p-0" onClick={prev} aria-label="Previous">
            <ChevronLeft className="h-6 w-6" />
          </Button>
        </div>
        <div className="absolute inset-y-0 right-2 flex items-center">
          <Button type="button" variant="ghost" className="h-10 w-10 p-0" onClick={next} aria-label="Next">
            <ChevronRight className="h-6 w-6" />
          </Button>
        </div>
      </div>
    </div>
  );
}
