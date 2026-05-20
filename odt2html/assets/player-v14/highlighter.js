/* odt2html player word highlighter
** Copyright 2014--2017, Trinity College Computing Center
**
** This file is part of Odt2html.
**
** Odt2html is free software: you can redistribute it and/or modify
** it under the terms of the GNU General Public License as published by
** the Free Software Foundation, either version 3 of the License, or
** (at your option) any later version.
**
** Odt2html is distributed in the hope that it will be useful,
** but WITHOUT ANY WARRANTY; without even the implied warranty of
** MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
** GNU General Public License for more details.
**
** You should have received a copy of the GNU General Public License
** along with Odt2html. If not, see <http://www.gnu.org/licenses/>.
*/

"use strict";

var style = document.createElement("style");
style.type = "text/css";
style.appendChild(document.createTextNode("\
	DIV.player_text SPAN.w:hover {outline: 1px black dotted} \
	DIV.player_text SPAN.highlighted {background-color: yellow} \
	"));
document.head.appendChild(style);

function Highlighter(player_id, scroller) {
	var this_this = this;
	this.scroller = scroller;
	this.player_id = player_id;

	this.span_count = 0;
	this.prev_paragraph = null;		/* element currently highlighted */
	this.prev_word = null;			/* element currently highlighted */
	this.scroll_remaining = 0;
	this.scroll_timer = null;

	/* Find the block of text to be highlighted. */
	this.text_container = document.getElementById("Text" + player_id);

	/* Set a class on the text block in case we want to style it. */
	this.text_container.className = this.text_container.className + " player_text";

	/* Wrap each word in the text block in a span with an id. */
	if(document.getElementById("W"+this.player_id+"0") === null)
		this.span_words(this.text_container);

	/* Add handler so that the user can click on the worrds to move the player position. */
	var text_click_regexp = new RegExp('^W' + player_id + '(\\d+)$');
	this.text_click_closure = function(event) {
		//console.log("text_click:", event.target.id);
		var match = event.target.id.match(text_click_regexp);
		if(match !== null) {
			var word_index = parseInt(match[1]);
			parent.players.wordclick(word_index);
		}
	}
	this.text_container.addEventListener('click', this.text_click_closure, false);
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

		/* Scroll the current paragraph into view if it is not already. */
		var paragraph = word.parentElement;
		if(paragraph !== this.prev_paragraph) {
			console.log("scroll: new paragraph");

			var paragraph_middle = (paragraph.offsetTop + paragraph.offsetHeight / 2);
			console.log("paragraph_middle=" + paragraph_middle);

			/* FIXME: close, but doesn't correctly account for everything */
			var scroller_middle = (this.scroller.parentElement.offsetHeight / 2 - this.scroller.parentElement.offsetTop);
			console.log("scroller_middle=" + scroller_middle);

			var scroll_target = (paragraph_middle - scroller_middle);
			console.log("scroll_target=" + scroll_target);
			this.scroll_remaining = scroll_target >= 0 ? Math.round(scroll_target - this.scroller.scrollTop) : 0;
			console.log("scroll_remaining=" + this.scroll_remaining);

			if(this.scroll_remaining && this.scroll_timer === null) {
				var this_this = this;
				this.scroll_timer = setInterval(function() {
					if(this_this.scroll_remaining > 0) {
						//console.log("scroll: down");
						this_this.scroller.scrollTop++;
						this_this.scroll_remaining--;
					} else if(this_this.scroll_remaining < 0) {
						//console.log("scroll: up");
						this_this.scroller.scrollTop--;
						this_this.scroll_remaining++;
					} else {
						//console.log("scroll: arrived");
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

