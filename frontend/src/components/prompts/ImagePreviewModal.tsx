import { Dialog, DialogContent } from "../ui/dialog";

export function ImagePreviewModal({ src, onClose }: { src: string | null; onClose: () => void }) {
  return (
    <Dialog open={Boolean(src)} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-6xl p-2" showCloseButton>
        {src && <img src={src} className="max-h-[86vh] w-full object-contain" />}
      </DialogContent>
    </Dialog>
  );
}
