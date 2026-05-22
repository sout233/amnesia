declare module 'turndown' {
	export interface TurndownOptions {
		headingStyle?: 'setext' | 'atx';
		hr?: string;
		bulletListMarker?: '-' | '*' | '+';
		codeBlockStyle?: 'indented' | 'fenced';
		emDelimiter?: '_' | '*';
		strongDelimiter?: '**' | '__';
		linkStyle?: 'inlined' | 'referenced';
		linkReferenceStyle?: 'full' | 'collapsed' | 'shortcut';
		br?: string;
	}

	export default class TurndownService {
		constructor(options?: TurndownOptions);
		turndown(input: string): string;
	}
}
