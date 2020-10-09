# caps

## Viewing the prototype

Visit <https://mysociety.github.io/caps>.

## Building the prototype locally

The prototype is built with Jekyll. If you don’t already have Jekyll installed on your computer, you’ll need:

* a working [Ruby](https://www.ruby-lang.org/en/) environment
* [Bundler](https://bundler.io/)

You can then install Jekyll (as part of the `github-pages` Gem) by running this, inside the project directory:

    bundle install

With Jekyll installed through Bundler, you can build the site with:

    bundle exec jekyll serve --baseurl ''

If that’s a bit long to type, and you have Make installed (you probably do), then you can use our shortcut:

    make run

Jekyll will process the HTML templates and Sass files, and serve the site locally, at <http://localhost:4000> by default.
