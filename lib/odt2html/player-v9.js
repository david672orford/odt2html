/* odt2html player frontend */

"use strict";

/* IE does not define console unless the debugger is active! */
if(!window.console) window.console = {};
if(!window.console.log) window.console.log = function () { };

/* Load the backend if it is not loaded already. If this page is
   framed, it will be loaded into the parent. */
window.addEventListener('DOMContentLoaded', function () {
	var basedir = "../lib/odt2html";

	if(parent.document.getElementById("player_backends")) {
		console.log("Backend already loaded.");
	} else {
		console.log("Loading backend...");

		var script = parent.document.createElement("script");
		script.id = "player_backends";
		script.src = basedir + "/player-backend-v9.js";
		script.type = "text/javascript";
		parent.document.head.appendChild(script);
	
		var link = parent.document.createElement("link");
		link.href = basedir + "/player-backend-v9.css";
		link.rel = "stylesheet";
		link.type = "text/css";
		parent.document.head.appendChild(link);
	}
}, false);

function bgplay(url) {
	parent.players.bgplay(url);
}

function play_audio(url, title, highlight_track, player_id) {
	var highlighter = null;
	if(highlight_track) {
		highlighter = new Highlighter(player_id, document.body);
	}
	parent.players.play_audio(url, title, highlight_track, highlighter);
}

function play_video(url, title, captions, player_id) {
	parent.players.play_video(url, title, captions);
}

/*==================================================
** Word Highlighter
**================================================*/
function Highlighter(player_id, scroller) {
	var this_this = this;
	this.scroller = scroller;
	this.player_id = player_id;

	this.span_count = 0;
	this.prev_paragraph = null;		/* element currently highlighted */
	this.prev_word = null;			/* element currently highlighted */
	this.scroll_remaining = 0;
	this.scroll_timer = null;

	/* Enable any special styling of the block of text being read */
	this.text_container = document.getElementById("Text" + player_id);
	this.text_container.className = this.text_container.className + " player_text";

	this.text_click_regexp = new RegExp('^W' + player_id + '(\\d+)$');
	this.text_click_closure = function(event) { this_this.text_click(event); }
	this.text_container.addEventListener('click', this.text_click_closure, false);

	if(document.getElementById("W"+this.player_id+"0") === null)
		this.span_words(this.text_container);
}

/* Put a span tag with an ID around each word */
Highlighter.prototype.span_words = function(el) {
	var el = el.firstChild;
	while(el !== null) {
		var next_el = el.nextSibling;
		if(el.nodeType === Node.TEXT_NODE) {
			var frag = document.createDocumentFragment();
			var re = /([а-яёА-ЯЁ\ẃ]+)|([^а-яёА-ЯЁ\ẃ]+)/g;
			var text = el.nodeValue;
			var m;
			while(m = re.exec(text)) {
				if(m[1] !== undefined) {	/* word */
					var span = document.createElement("span");
					span.id = "W" + this.player_id + this.span_count;
					span.className = "w";
					this.span_count++;
					span.appendChild(document.createTextNode(m[1]));
					frag.appendChild(span);
				} else {					/* spaces, punctuation, etc. */
					frag.appendChild(document.createTextNode(m[2]));
				}
			}
			el.parentNode.replaceChild(frag, el);
		} else if(el.nodeType === Node.ELEMENT_NODE) {
			this.span_words(el);
		}
		el = next_el;
	}
}

/* Highlight a word specified by zero-based index. Unhighlight any
   word currently highlighted. An index of null will leave no word
   highlighted. */
Highlighter.prototype.highlight = function(word_index) {
	if(this.prev_word !== null) {				/* clear previous word highlighting */
		this.prev_word.className = "w";
		this.prev_word = null;
	}

	if(word_index !== null) {					/* create new word highlighting */
		var word = document.getElementById("W"+this.player_id+word_index);
		word.className = "w highlighted";

		var paragraph = word.parentElement;		/* highlight paragraph too */
		if(paragraph !== this.prev_paragraph) {
			console.log("scroll: new paragraph");
			var scroll_target = paragraph.offsetTop + paragraph.offsetHeight / 2 - this.scroller.offsetHeight / 2 - this.scroller.offsetTop;
			this.scroll_remaining = Math.round(scroll_target - this.scroller.scrollTop);
			if(this.scroll_remaining && this.scroll_timer === null) {
				var this_this = this;
				this.scroll_timer = setInterval(function() {
					if(this_this.scroll_remaining > 0) {
						console.log("scroll: down");
						this_this.scroller.scrollTop++;
						this_this.scroll_remaining--;
					} else if(this_this.scroll_remaining < 0) {
						console.log("scroll: up");
						this_this.scroller.scrollTop--;
						this_this.scroll_remaining++;
					} else {
						console.log("scroll: arrived");
						clearInterval(this_this.scroll_timer);
						this_this.scroll_timer = null;
					}
				}, 5);		/* 200 steps per second */
			}

			this.prev_paragraph = paragraph;
		}

		this.prev_word = word;
	}
}

Highlighter.prototype.close = function() {
	console.log("Closing highlighter...");

	/* If a word is highlighted, remove the highlighting. */
	this.highlight(null);

	/* Disable special styling of the block of text being read */
	this.text_container.className = this.text_container.className.replace(" player_text","");

	/* Remove our handler which made the words clickable. */
	this.text_container.removeEventListener('click', this.text_click_closure, false);

	this.text_container = null;
}

/* If the user has clicked on a word, move the player to it. */
Highlighter.prototype.text_click = function(event) {
	//console.log("text_click:", event.target.id);
	if(this.text_click_regexp !== null) {
		var match = event.target.id.match(this.text_click_regexp);
		if(match !== null) {
			var word_index = parseInt(match[1]);
			parent.players.wordclick(word_index);
		}
	}

}

