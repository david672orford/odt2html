/* Javascript functions for use with odt2html when the document
   includes links to audio and video files */

/* IE does not define console unless the debugger is active! */
if (!window.console) window.console = {};
if (!window.console.log) window.console.log = function () { };

/* Convenience function inspired by LXML */
function E(name) {
	var el = document.createElement(name);
	for(var i=1; i<arguments.length; i++) {
		var arg = arguments[i];
		switch(typeof(arg)) {
			case 'string':
				el.appendChild(document.createTextNode(arg));
				break;
			case 'object':
				if('nodeType' in arg) {
					el.appendChild(arg);
				} else {
					for(var name in arg) {
						if(name === 'className')
							el.setAttribute('class', arg[name]);
						else
							el.setAttribute(name, arg[name]);
					}
				}
				break;
			default:
				console("unhandled case:", typeof(arg));
				break;
		}
	}
	return el;
}

/* Override this to actually receive data */
window.analytics = function() {};

/*==========================================
** Functions called from page
**========================================*/

/* Invoke background audio player */
var bg_player = null;
function bgplay(url) {
	console.log('bgplay("' + url + '")');
	if(bg_player === null) {
		bg_player = new AudioPlayer();
	}
	bg_player.play_url(url, null);
	analytics('TD Sound', 'play', url);
}

/* Invoke forground audio player with GUI controls */
var audio_player = null;
function play_audio(url, title, highlight, player_id) {
	console.log('play_audio("' + url + '")');
	if(video_player !== null) {
		video_player.close();
	}
	if(audio_player === null || audio_player.closed) {
		audio_player = new GuiAudioPlayer();
	}
	audio_player.play_url(url, title, highlight, player_id);
}

/* Invoke forground video player with GUI controls */
var video_player = null;
function play_video(url, title, captions, player_id) {
	console.log('play_video("' + url + '")');
	if(audio_player !== null) {
		audio_player.close();
	}
	if(video_player === null || video_player.closed) {
		video_player = new VideoPlayer();
	}
	video_player.play_url(url, title, captions, player_id);
}

/*==========================================
** Audio Player Without Controls
**========================================*/
function AudioPlayer() {
	this.audio = E("audio");

	this.source_ogg = E("source");
	this.source_ogg.type = "audio/ogg";
	this.audio.appendChild(this.source_ogg);

	this.source_mp3 = E("source");
	this.source_mp3.type = "audio/mpeg";
	this.audio.appendChild(this.source_mp3);

	this.webvtt = null;
}

/* Set the URL of the audio files for the player to play.
   If the extension is .mp3, then assume the file is available only
   in MP3 format (as external files frequently are).
   If the extesion is .ogg, assume it is also available as MP3.
*/
AudioPlayer.prototype.play_url = function(url) {
	if(url.substr(-4) === ".mp3") {			/* MP3 only */
		this.source_ogg.removeAttribute("src");
		this.source_mp3.src = url;
	} else if(url.indexOf(".ogg#") != -1) {		/* fragment */
		this.source_ogg.src = url;
		this.source_mp3.src = url.replace(".ogg#",".mp3#");
	} else {
		this.source_ogg.src = url;
		this.source_mp3.src = url.replace(".ogg", ".mp3");
	}
	if(this.webvtt !== null) {
		this.video.removeChild(this.webvtt);
		this.webvtt = null;
	}
	this.audio.load();
	this.audio.play();
}

/*==================================================
** Wrapper for AudioPlayer which adds GUI controls
**================================================*/
function GuiAudioPlayer() {
	var this_this = this;
	this.closed = false;
	this.url = null;
	this.text_container = null;
	this.highlighter = null;
	this.page_click_regexp = null;

	this.div = E("div");
	this.div.className = "audio_player";

	this.player = new AudioPlayer();
	this.player.audio.controls = true;
	this.div.appendChild(this.player.audio);

	this.menu = new PlayerMenu([
		"Download OGG",
		"Download MP3"
		]);
	this.div.appendChild(this.menu.menu_btn);
	this.div.appendChild(this.menu.menu);

	var close_btn = E("img", { className: "close_btn", src: "../lib/odt2html/btn_close.svg" });
	close_btn.onclick = function() { this_this.close(); };
	this.div.appendChild(close_btn);

	document.body.appendChild(this.div);
	document.body.className += " with_audio";

	var this_this = this;
	this.player.audio.addEventListener("ended", function() {
		analytics('Audio', 'ended', this_this.url);
	}, true);
	this.player.audio.addEventListener("paused", function() {
		analytics('Audio', 'paused', this_this.url, this_this.player.audio.currentTime);
	}, true);
	this.player.audio.addEventListener("play", function() {
		analytics('Audio', 'resumed', this_this.url, this_this.player.audio.currentTime);
	}, true);

	this.page_click_closure = function(event) { this_this.page_click(event); }
	window.addEventListener('click', this.page_click_closure);
}

/* If the user has clicked on a word, move the player to it. */
GuiAudioPlayer.prototype.page_click = function(event) {
	//console.log("page_click:", event.target.id);

	this.menu.hide();

	if(this.page_click_regexp !== null) {
		var match = event.target.id.match(this.page_click_regexp);
		if(match !== null) {
			word_index = parseInt(match[1]);
			var startTime = this.player.audio.textTracks[0].cues[word_index].startTime;
			console.log("text click:", word_index, startTime);
			this.player.audio.currentTime = startTime + 0.001;
		}
	}

}

/* Set the URL for the GUI player to play */
GuiAudioPlayer.prototype.play_url = function(url, title, highlight_track, player_id) {
	this.url = url;
	analytics('Audio', 'play', this.url);

	this.clear_highlighting();
	this.page_click_regexp = null;

	/* Start playing */
	this.player.play_url(url);

	/* Is there a WebVTT metadata track which tells us which words to highlight when? */
	if(highlight_track !== null) {
		this.text_container = document.getElementById("Text" + player_id);
		this.text_container.className = this.text_container.className + " player_text";
		this.highlighter = new Highlighter(this.text_container, player_id, document.body);

		/* Add the cue track to the <audio> tag */
		this.webvtt = E("track", {src: highlight_track, kind: 'metadata', label: 'cues', default:'default'});
		this.player.audio.appendChild(this.webvtt);
		var this_this = this;
		this.webvtt.addEventListener("cuechange", function(event) {
			var cues = this.track.activeCues;
			var cue = cues.length ? cues[0].id : null;
			console.log("cue:", cue);
			this_this.highlighter.highlight(cue);
		});
		this.player.audio.textTracks[0].mode = 'showing';

		this.page_click_regexp = new RegExp('^W' + player_id + '(\\d+)$');
	}

	/* Set links in download menu */
	if(this.player.source_ogg.hasAttribute("src")) {
		this.menu.options[0].href = this.player.source_ogg.src;
	} else {
		this.menu.options[0].removeAttribute("href");
	}
	this.menu.options[1].href = this.player.source_mp3.src;

}

GuiAudioPlayer.prototype.clear_highlighting = function() {
	if(this.highlighter) {
		this.highlighter.highlight(null);
		this.highlighter = null;
		this.text_container.className = this.text_container.className.replace(" player_text","");
		this.text_container = null;
	}
}

GuiAudioPlayer.prototype.close = function() {
	console.log("Close audio player");
	if(!this.closed) {
		analytics('Audio', 'closed', this.url, this.player.audio.currentTime);
		document.body.removeChild(this.div);
		document.body.className = document.body.className.replace(" with_audio", "");
		window.removeEventListener('click', this.page_click_closure);
		this.clear_highlighting();
		this.closed = true;
	}
}

/*==============================
** Video Player with Controls
**============================*/
function VideoPlayer() {
	var this_this = this;
	this.closed = false;
	this.url = null;

	this.div = E("div", {className: "video_player"});

	this.titlebar = E("div", {className: "titlebar"});
	this.div.appendChild(this.titlebar);

	this.titlebar.draggable = true;
	this.bottom_left_x = 0;
	this.bottom_left_y = 0;
	this.prev_x = null;
	this.prev_y = null;
	this.titlebar.addEventListener('dragstart', function(event) {
		console.log("drag start: " + event.clientX + ", " + event.clientY);
		this_this.prev_x = event.clientX;
		this_this.prev_y = event.clientY;
	});
	this.titlebar.addEventListener('drag', function(event) {
		console.log("drag: " + event.clientX + ", " + event.clientY);
		if(event.clientX != 0 && event.clientY != 0) {
			this_this.bottom_left_x += (event.clientX - this_this.prev_x);
			this_this.bottom_left_y += (this_this.prev_y - event.clientY);
			this_this.prev_x = event.clientX;
			this_this.prev_y = event.clientY;
			this_this.div.style.left =   this_this.bottom_left_x + "px";
			this_this.div.style.bottom = this_this.bottom_left_y + "px"; 
		}
	});

	var close_btn = E("img", { className: "close_btn", src: "../lib/odt2html/btn_close.svg" });
	close_btn.onclick = function() { this_this.close(); };
	this.titlebar.appendChild(close_btn);

	this.menu = new PlayerMenu([
		"Download Webm",
		"Download MP4"
		]);
	this.titlebar.appendChild(this.menu.menu_btn);
	this.titlebar.appendChild(this.menu.menu);

	this.title = E("div", {className: "titlebar_text"});
	this.titlebar.appendChild(this.title);

	this.video = E("video", {controls: true});
	this.div.appendChild(this.video);

	this.source_webm = E("source", {type: "video/webm"});
	this.video.appendChild(this.source_webm);

	this.source_mp4 = E("source", {type: "video/mp4"});
	this.video.appendChild(this.source_mp4);

	this.webvtt = null;

	document.body.appendChild(this.div);
	document.body.className += " with_video";

	var this_this = this;
	this.video.addEventListener("ended", function() {
		analytics('Video', 'ended', this_this.url);
	}, true);
	this.video.addEventListener("paused", function() {
		analytics('Video', 'paused', this_this.url, this_this.video.currentTime);
	}, true);
	this.video.addEventListener("play", function() {
		analytics('Video', 'resumed', this_this.url, this_this.video.currentTime);
	}, true);

	this.page_click_closure = function(event) { this_this.page_click(event); }
	window.addEventListener('click', this.page_click_closure);
}

VideoPlayer.prototype.page_click = function(event) {
	//console.log("page_click:", event.target.id);
	this.menu.hide();
}

/* Set the URL of the video files for the player to play.
   If the extension is .mp4, then assume the file is available only
   in MP4 format (as external files frequently are).
   If the extension is .webm, assume it is also available as MP4.
*/
VideoPlayer.prototype.play_url = function(url, title, captions, player_id) {
	analytics('Video', 'play', url);
	this.url = url;
	this.title.innerHTML = title;
	if(url.substr(-4) === ".mp4") {
		this.source_webm.removeAttribute("src");
		this.source_mp4.src =  url;
		this.menu.options[0].removeAttribute("href");
	} else {
		this.source_webm.src = url;
		this.source_mp4.src =  url.replace(".webm",".mp4");
		this.menu.options[0].href =  this.source_webm.src;
	}
	if(this.webvtt !== null) {
		this.video.removeChild(this.webvtt);
		this.webvtt = null;
	}
	if(captions) {
		this.webvtt = E("track", {src: captions, kind: 'captions', label: 'English'});
		this.video.appendChild(this.webvtt);
	}
	this.menu.options[1].href =  this.source_mp4.src;
	this.video.load();
	this.video.play();
}

VideoPlayer.prototype.close = function() {
	console.log("Close video player");
	if(!this.closed) {
		analytics('Video', 'closed', this.url, this.video.currentTime);
		document.body.removeChild(this.div);
		document.body.className = document.body.className.replace(" with_video", "");
		window.removeEventListener('click', this.page_click_closure);
		this.closed = true;
	}
}

/*==============================
** Player menu
**============================*/
function PlayerMenu(option_labels) {
	var this_this = this;

	/* Button which opens and closes the menu */
	this.menu_btn = E("img");
	this.menu_btn.src = "../lib/odt2html/btn_menu.svg";
	this.menu_btn.className = "menu_btn";
	this.menu_btn.onclick = function(event) {
		//console.log("Menu button clicked.");
		this_this.menu.style.display = this_this.menu.style.display == "none" ? "block" : "none";
		event.stopPropagation();
		}

	/* The menu itself */
	this.menu = E("div");
	this.menu.className = "player_menu";
	this.menu.style.display = "none";

	this.options = [];
	for(var i=0; i < option_labels.length; i++) {
		var option = E("a");
		option.appendChild(document.createTextNode(option_labels[i]));
		option.onclick = function() {
			this_this.menu.style.display = "none";
			return true;
		}
		option.download = "";
		this.menu.appendChild(option);
		this.options[i] = option;
	}
}

PlayerMenu.prototype.hide = function() {
	this.menu.style.display = "none";
}

/*==================================================
** Word Highlighter
**================================================*/
function Highlighter(text_container, player_id, scroller) {
	this.text_container = text_container;
	this.scroller = scroller;
	this.player_id = player_id;
	this.span_count = 0;
	this.prev_paragraph = null;		/* element currently highlighted */
	this.prev_word = null;			/* element currently highlighted */
	this.scroll_remaining = 0;
	this.scroll_timer = null;
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
	if(this.prev_word !== null) {			/* clear previous word highlighting */
		this.prev_word.className = "w";
		this.prev_word = null;
	}

	if(word_index !== null) {				/* create new word highlighting */
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

