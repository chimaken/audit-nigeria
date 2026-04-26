/** Short labels for non-technical readers (underlying API values unchanged). */

export function consensusStatusLabel(status: string): string {
  switch (status) {
    case "VERIFIED":
      return "Verified";
    case "DISPUTED":
      return "Needs review";
    case "PENDING":
      return "Waiting";
    case "NO_CLUSTER":
      return "No sheet yet";
    default:
      return status;
  }
}
