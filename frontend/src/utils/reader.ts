/**
 * Extracts the chapter number from a URL.
 * Supports /chapter/{n} (most sites) and Fanfox's /c{n}/ format.
 * Returns null if no numeric chapter segment is found.
 */
export function chapterNumFromUrl(url: string): number | null {
	const standard = url.match(/\/chapter\/([\d.]+)(?=[/?#]|$)/);
	if (standard) return parseFloat(standard[1]);
	const fanfox = url.match(/\/c([\d.]+)\//);
	if (fanfox) return parseFloat(fanfox[1]);
	return null;
}

/**
 * Replaces the chapter number in `currentUrl` with `newNum`.
 * Handles /chapter/{n} and Fanfox's /c{n}/ formats.
 */
export function buildChapterUrl(currentUrl: string, newNum: number): string {
	if (/\/chapter\/([\d.]+)(?=[/?#]|$)/.test(currentUrl))
		return currentUrl.replace(/\/chapter\/([\d.]+)(?=[/?#]|$)/, `/chapter/${newNum}`);
	if (/\/c[\d.]+\//.test(currentUrl))
		return currentUrl.replace(/\/c([\d.]+)\//, `/c${newNum}/`);
	return currentUrl;
}
