/** Short labels for non-technical readers (underlying API values unchanged). */

/** Plain-language hint for `review_reason` from GET /results/pu/{id}. */
export function consensusReviewReasonLabel(reason: string | null | undefined): string {
  switch (reason) {
    case "insufficient_uploads":
      return "Upload at least two photos of this sheet so we can compare readings.";
    case "extraction_failed":
      return "We could not read vote figures from enough photos (timeout, blur, or model error).";
    case "high_variance":
      return "The model read different numbers on different photos—no two readings matched.";
    case "figures_words_mismatch":
      return "Written numbers (words) and digit columns disagree on the sheet.";
    case "arithmetic_inconsistent":
      return "Party vote columns and the totals row do not add up the INEC way.";
    default:
      return reason?.replace(/_/g, " ") || "Under review";
  }
}

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
