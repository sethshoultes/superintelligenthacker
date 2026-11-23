// official-embed (site-kit#573): the YouTube facade. Page load fetches nothing from YouTube. This script only turns the play
// button on; one click swaps the poster for the no-cookie iframe, and that press is what starts the video.
(function () {
  var ID = /^[A-Za-z0-9_-]{11}$/;
  function wire(box) {
    var id = box.getAttribute("data-video-id");
    var button = box.querySelector(".official-embed-youtube__play");
    if (!button || !ID.test(id || "")) return;
    button.hidden = false;
    button.addEventListener("click", function () {
      var frame = document.createElement("iframe");
      frame.src = "https://www.youtube-nocookie.com/embed/" + id + "?rel=0&autoplay=1";
      frame.title = box.getAttribute("data-title") || "Video";
      frame.allow = "autoplay; encrypted-media; picture-in-picture; fullscreen";
      frame.setAttribute("allowfullscreen", "");
      frame.referrerPolicy = "strict-origin-when-cross-origin";
      frame.className = "official-embed-youtube__frame";
      box.querySelector(".official-embed-youtube__poster").remove();
      button.replaceWith(frame);
      frame.focus();
    });
  }
  Array.prototype.forEach.call(document.querySelectorAll(".official-embed-youtube"), wire);
})();
