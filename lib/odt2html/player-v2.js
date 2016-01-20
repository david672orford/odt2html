/* Javascript functions for use with odt2html when the document includes
   links to audio and video files */

/* IE does not define console unless the debugger is active! */
if (!window.console) window.console = {};
if (!window.console.log) window.console.log = function () { };

/* Short alias for function for creating HTML DOM elements */
function E(tag) {
	return document.createElement(tag);
	}

/* Background audio player */
var bg_player = null;
function bgplay(url) {
	console.log('bgplay("' + url + '")');
	if(bg_player === null) {
		bg_player = new AudioPlayer();
	}
	bg_player.play_url(url);
}

/* Forground audio player with GUI controls */
var audio_player = null;
function play_audio(url, title) {
	console.log('play_audio("' + url + '")');
	if(video_player !== null) {
		video_player.close();
	}
	if(audio_player === null || audio_player.closed) {
		audio_player = new GuiAudioPlayer();
	}
	audio_player.play_url(url, title);
}

/* Forground video player with GUI controls */
var video_player = null;
function play_video(url, title) {
	console.log('play_video("' + url + '")');
	if(audio_player !== null) {
		audio_player.close();
	}
	if(video_player === null || video_player.closed) {
		video_player = new VideoPlayer();
	}
	video_player.play_url(url, title);
}

window.onclick = function(event) {
	console.log("Click outside menu.");
	if(audio_player)
		audio_player.menu.hide();
	if(video_player)
		video_player.menu.hide();
}

/* Audio Player Without Controls */
function AudioPlayer() {
	this.audio = E("audio");

	this.source_ogg = E("source");
	this.source_ogg.type = "audio/ogg";
	this.audio.appendChild(this.source_ogg);

	this.source_mp3 = E("source");
	this.source_mp3.type = "audio/mpeg";
	this.audio.appendChild(this.source_mp3);
}

/* Set the URL of the audio files for the player to play. The audio
   file extension should be omitted from the URL. */
AudioPlayer.prototype.play_url = function(url) {
	if(url.substr(-4) === ".mp3") {
		this.source_ogg.removeAttribute("src");
		this.source_mp3.src = url;
	} else {
		this.source_ogg.src = url + ".ogg";
		this.source_mp3.src = url + ".mp3";
	}
	this.audio.load();
	this.audio.play();
}

/* Wrapper for AudioPlayer which adds GUI controls */
function GuiAudioPlayer() {
	var this_this = this;
	this.closed = false;

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

	this.close_btn = E("img");
	this.close_btn.src = "../lib/odt2html/btn_close.svg";
	this.close_btn.className = "close_btn";
	this.close_btn.onclick = function() { this_this.close(); };
	this.div.appendChild(this.close_btn);

	document.body.appendChild(this.div);
}

/* Set the URL for the GUI player to play */
GuiAudioPlayer.prototype.play_url = function(url, title) {
	this.player.play_url(url);
	if(this.player.source_ogg.hasAttribute("src")) {
		this.menu.options[0].href = this.player.source_ogg.src;
	} else {
		this.menu.options[0].removeAttribute("href");
	}
	this.menu.options[1].href = this.player.source_mp3.src;
}

GuiAudioPlayer.prototype.close = function() {
	console.log("Close audio player");
	if(!this.closed) {
		document.body.removeChild(this.div);
		this.closed = true;
	}
}

/* Video Player with Controls */
function VideoPlayer() {
	var this_this = this;
	this.closed = false;

	this.div = E("div");
	this.div.className = "video_player";

	this.titlebar = E("div");
	this.titlebar.className = "titlebar";
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

	this.close_btn = E("img");
	this.close_btn.src = "../lib/odt2html/btn_close.svg";
	this.close_btn.className = "close_btn";
	this.close_btn.onclick = function() { this_this.close(); };
	this.titlebar.appendChild(this.close_btn);

	this.menu = new PlayerMenu([
		"Download Webm",
		"Download MP4"
		]);
	this.titlebar.appendChild(this.menu.menu_btn);
	this.titlebar.appendChild(this.menu.menu);

	this.title = E("div");
	this.title.className = "titlebar_text";
	this.titlebar.appendChild(this.title);

	this.video = E("video");
	this.video.controls = true;
	this.div.appendChild(this.video);

	this.source_webm = E("source");
	this.source_webm.type = "video/webm";
	this.video.appendChild(this.source_webm);

	this.source_mp4 = E("source");
	this.source_mp4.type = "video/mp4";
	this.video.appendChild(this.source_mp4);

	document.body.appendChild(this.div);
	document.body.className = "with_video";
}

/* Set the URL of the video files for the player to play. The video
   file extension should be omitted from the URL. */
VideoPlayer.prototype.play_url = function(url, title) {
	if(url.substr(-4) === ".mp4") {
		this.source_webm.removeAttribute("src");
		this.source_mp4.src =  url;
		this.menu.options[0].removeAttribute("href");
	} else {
		this.source_webm.src = url + ".webm";
		this.source_mp4.src =  url + ".mp4";
		this.menu.options[0].href =  this.source_webm.src;
	}
	this.menu.options[1].href =  this.source_mp4.src;
	this.video.load();
	this.video.play();
	this.title.innerHTML = title;
}

VideoPlayer.prototype.close = function() {
	console.log("Close video player");
	if(!this.closed) {
		document.body.removeChild(this.div);
		document.body.className = "";
		this.closed = true;
	}
}

/* Player menu */
function PlayerMenu(option_labels) {
	var this_this = this;

	/* Button which opens and closes the menu */
	this.menu_btn = E("img");
	this.menu_btn.src = "../lib/odt2html/btn_menu.svg";
	this.menu_btn.className = "menu_btn";
	this.menu_btn.onclick = function(event) {
		console.log("Menu button clicked.");
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
