/**
 * Extracts the chapter number from a URL.
 * Supports /chapter/{n} (most sites), /chapter-{n} (VortexScans) and Fanfox's /c{n}/ format.
 * Returns null if no numeric chapter segment is found.
 */
export function chapterNumFromUrl(url: string): number | null {
	const standard = url.match(/\/chapter[/-]([\d.]+)(?=[/?#]|$)/i);
	if (standard) return parseFloat(standard[1]);
	const fanfox = url.match(/\/c([\d.]+)\//);
	if (fanfox) return parseFloat(fanfox[1]);
	return null;
}

/**
 * Replaces the chapter number in `currentUrl` with `newNum`.
 * Handles /chapter/{n}, /chapter-{n} (VortexScans) and Fanfox's /c{n}/ formats,
 * preserving the original separator (slash or hyphen).
 *
 * Returns `null` for Fanfox-style volume-prefixed URLs (pattern: /vNN/cNNN/) because
 * the volume segment cannot be determined client-side — use the /reader/fanfox-chapter
 * endpoint instead.
 */
export function buildChapterUrl(currentUrl: string, newNum: number): string | null {
	if (/\/chapter[/-]([\d.]+)(?=[/?#]|$)/i.test(currentUrl))
		return currentUrl.replace(/\/chapter([/-])[\d.]+(?=[/?#]|$)/i, `/chapter$1${newNum}`);
	if (/\/v\d+\/c[\d.]+\//.test(currentUrl))
		return null;
	if (/\/c[\d.]+\//.test(currentUrl))
		return currentUrl.replace(/\/c([\d.]+)\//, `/c${newNum}/`);
	return currentUrl;
}
