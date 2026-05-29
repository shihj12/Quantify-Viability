// Zero-dependency helper to build an ImageData from a Uint8ClampedArray.
//
// Newer TS lib.dom types Uint8ClampedArray as generic over ArrayBufferLike,
// while the ImageData constructor requires ArrayBuffer specifically. Our buffers
// are always backed by a real (non-shared) ArrayBuffer, so this narrows the type
// with no runtime cost.

export function toImageData(
  data: Uint8ClampedArray,
  width: number,
  height: number,
): ImageData {
  return new ImageData(data as Uint8ClampedArray<ArrayBuffer>, width, height);
}
