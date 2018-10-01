"use strict";

var zoomed_image = null;

window.addEventListener('DOMContentLoaded', function () {

	/* Load CSS */
	var el = document.createElement("link");
	el.rel = "stylesheet";
	el.type = "text/css";
	el.href = "/lib/odt2html/zoom_image-v1.css";
	document.head.appendChild(el);

	/* Add click handlers to the image links */
	var links = document.getElementsByTagName("a");
	for(var i=0; i < links.length; i++) {
		var link = links[i];
		if(link.hash === "#zoom_image") {
			link.addEventListener('click', zoom_image);
		}
	}

	/* If the user clicks elsewhere anywhere, remove the popup image. */
	document.addEventListener('click', function() {
		if(zoomed_image !== null) {
			document.body.removeChild(zoomed_image);
			zoomed_image = null;
		}
	}, true);

});

function zoom_image(event) {
	console.log(event);
	var target = event.target;
	if(target.tagName === "A")
		target = target.getElementsByTagName("img")[0];

	if(zoomed_image !== null)
		document.body.removeChild(zoomed_image);

	var window_width = document.documentElement.clientWidth;
	var window_height = document.documentElement.clientHeight;

	var aspect_ration = (target.clientWidth / target.clientHeight);
	var popup_width = Math.min(window_width * 0.8, window_height * aspect_ration * 0.8);
	var popup_height = (popup_width / aspect_ration);
	var left_margin = ((window_width - popup_width) / 2.0);
	var top_margin = ((window_height - popup_height) / 2.0);

	zoomed_image = document.createElement("img");
	zoomed_image.className = "zoomed_image";
	zoomed_image.src = target.src;
	zoomed_image.style.left =left_margin + "px";
	zoomed_image.style.top = top_margin + "px";
	zoomed_image.style.width = popup_width + "px";
	zoomed_image.style.height = popup_height + "px";
	document.body.appendChild(zoomed_image);

}
